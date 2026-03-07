#!/Applications/QGIS.app/Contents/MacOS/bin/python3
"""Batch export thematic maps from configured templates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFillSymbol,
    QgsGraduatedSymbolRenderer,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPage,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsMapLayer,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsRendererRange,
    QgsSingleSymbolRenderer,
    QgsLineSymbol,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsSymbol,
)

try:
    from osgeo import gdal
except Exception:  # pragma: no cover
    gdal = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export thematic maps in batch")
    parser.add_argument("--analysis-dir", default="data/outputs/wuhan_analysis")
    parser.add_argument("--themes", default="configs/thematic_maps.yaml")
    parser.add_argument("--output-dir", default="data/outputs/wuhan_analysis/maps")
    parser.add_argument("--project-path", default="data/outputs/wuhan_analysis/thematic_maps.qgz")
    parser.add_argument("--layout-prefix", default="Theme")
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("themes yaml root must be mapping")
    return data


def load_vec(path: Path, name: str) -> QgsVectorLayer:
    layer = QgsVectorLayer(str(path), name, "ogr")
    if not layer.isValid():
        raise RuntimeError(f"invalid layer: {path}")
    return layer


def apply_line_style(layer: QgsVectorLayer, color: str, width: str) -> None:
    symbol = QgsLineSymbol.createSimple({"line_color": color, "line_width": width})
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def apply_point_style(layer: QgsVectorLayer) -> None:
    symbol = QgsSymbol.defaultSymbol(layer.geometryType())
    if symbol is None:
        return
    symbol.setColor(QColor("#d7301f"))
    symbol.setSize(2.0)
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def format_label(low: float, high: float, is_last: bool) -> str:
    if is_last:
        return f"> {low:.2f}"
    return f"{low:.2f} - {high:.2f}"


def apply_grid_theme(layer: QgsVectorLayer, field: str, breaks: list[float], colors: list[str]) -> None:
    if layer.fields().indexFromName(field) < 0:
        raise RuntimeError(f"field not found for theme: {field}")

    if len(colors) != len(breaks) + 1:
        raise ValueError("colors count must equal breaks+1")

    ranges: list[QgsRendererRange] = []
    lower = -10**15
    for idx, upper in enumerate(breaks):
        symbol = QgsFillSymbol.createSimple(
            {"color": colors[idx], "outline_color": "#707070", "outline_width": "0.08"}
        )
        label = format_label(lower if idx > 0 else 0.0, float(upper), False)
        ranges.append(QgsRendererRange(float(lower), float(upper), symbol, label))
        lower = float(upper)

    symbol_last = QgsFillSymbol.createSimple(
        {"color": colors[-1], "outline_color": "#505050", "outline_width": "0.08"}
    )
    ranges.append(QgsRendererRange(float(lower), 10**15, symbol_last, format_label(float(lower), 0, True)))

    renderer = QgsGraduatedSymbolRenderer(field, ranges)
    layer.setRenderer(renderer)


def find_north_arrow() -> str:
    candidates = [
        "/Applications/QGIS.app/Contents/Resources/svg/arrows/NorthArrow_01.svg",
        "/Applications/QGIS.app/Contents/Resources/svg/arrows/NorthArrow_06.svg",
        "/Applications/QGIS.app/Contents/Resources/images/north_arrows/layout_default_north_arrow.svg",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return ""


def add_layout(
    project: QgsProject,
    layout_name: str,
    title: str,
    layers: list[QgsMapLayer],
    extent: QgsRectangle,
) -> QgsPrintLayout:
    manager = project.layoutManager()
    old = manager.layoutByName(layout_name)
    if old:
        manager.removeLayout(old)

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(layout_name)

    page = layout.pageCollection().pages()[0]
    page.setPageSize("A4", QgsLayoutItemPage.Orientation.Landscape)

    map_item = QgsLayoutItemMap(layout)
    map_item.attemptMove(QgsLayoutPoint(10, 16, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(235, 170, QgsUnitTypes.LayoutMillimeters))
    map_item.setLayers(layers)
    map_item.setExtent(extent)
    layout.addLayoutItem(map_item)

    title_item = QgsLayoutItemLabel(layout)
    title_item.setText(title)
    title_fmt = QgsTextFormat()
    title_fmt.setFont(QFont("Helvetica", 15))
    title_item.setTextFormat(title_fmt)
    title_item.adjustSizeToText()
    title_item.attemptMove(QgsLayoutPoint(10, 6, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(title_item)

    legend = QgsLayoutItemLegend(layout)
    legend.setLinkedMap(map_item)
    legend.attemptMove(QgsLayoutPoint(250, 20, QgsUnitTypes.LayoutMillimeters))
    legend.attemptResize(QgsLayoutSize(35, 80, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(legend)

    scalebar = QgsLayoutItemScaleBar(layout)
    scalebar.setLinkedMap(map_item)
    scalebar.setStyle("Single Box")
    scalebar.setUnits(QgsUnitTypes.DistanceKilometers)
    scalebar.setNumberOfSegments(4)
    scalebar.setNumberOfSegmentsLeft(0)
    scalebar.setUnitsPerSegment(2)
    scalebar.setUnitLabel("km")
    scalebar.applyDefaultSize()
    scalebar.attemptMove(QgsLayoutPoint(14, 181, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(scalebar)

    north_path = find_north_arrow()
    if north_path:
        north = QgsLayoutItemPicture(layout)
        north.setPicturePath(north_path)
        north.attemptMove(QgsLayoutPoint(270, 122, QgsUnitTypes.LayoutMillimeters))
        north.attemptResize(QgsLayoutSize(12, 18, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(north)

    footer = QgsLayoutItemLabel(layout)
    footer.setText("Data: OSM | Processing: GeoClaw-OpenAI")
    footer_fmt = QgsTextFormat()
    footer_fmt.setFont(QFont("Helvetica", 8))
    footer.setTextFormat(footer_fmt)
    footer.adjustSizeToText()
    footer.attemptMove(QgsLayoutPoint(210, 188, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(footer)

    manager.addLayout(layout)
    return layout


def export_layout(layout: QgsPrintLayout, output_png: Path) -> None:
    output_png.parent.mkdir(parents=True, exist_ok=True)
    if output_png.exists():
        output_png.unlink()
    world_file = output_png.with_suffix(".pgw")
    if world_file.exists():
        world_file.unlink()
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = 220
    # Avoid side effects from georeference/world-file updates on repeated runs.
    if hasattr(settings, "generateWorldFile"):
        settings.generateWorldFile = False
    if hasattr(settings, "exportMetadata"):
        settings.exportMetadata = False
    rc = exporter.exportToImage(str(output_png), settings)
    if rc != QgsLayoutExporter.Success:
        raise RuntimeError(f"failed to export layout: {output_png}")


def main() -> int:
    args = parse_args()

    if gdal is not None:
        def _gdal_error_handler(err_class: int, err_no: int, err_msg: str) -> None:
            text = (err_msg or "").strip()
            if err_no == 6 and "PNG driver does not support update access to existing datasets" in text:
                return
            sys.stderr.write(f"GDAL[{err_no}] {text}\n")

        gdal.PushErrorHandler(_gdal_error_handler)

    prefix = Path("/Applications/QGIS.app/Contents/MacOS")
    QgsApplication.setPrefixPath(str(prefix), True)
    app = QgsApplication([], False)
    app.initQgis()

    try:
        analysis_dir = Path(args.analysis_dir).resolve()
        output_dir = Path(args.output_dir).resolve()
        project_path = Path(args.project_path).resolve()
        themes_cfg = load_yaml(Path(args.themes).resolve())

        themes = themes_cfg.get("themes") or []
        if not isinstance(themes, list) or not themes:
            raise ValueError("themes list is empty")

        grid = load_vec(analysis_dir / "grid_clustered.gpkg", "Grid")
        roads = load_vec(analysis_dir / "roads_32650.gpkg", "Roads")
        water = load_vec(analysis_dir / "water_32650.gpkg", "Water")
        hospitals = load_vec(analysis_dir / "hospitals_32650.gpkg", "Hospitals")

        apply_line_style(roads, "#4d4d4d", "0.16")
        apply_line_style(water, "#1f78b4", "0.30")
        apply_point_style(hospitals)

        project = QgsProject.instance()
        project.clear()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:32650"))
        for lyr in [grid, water, roads, hospitals]:
            project.addMapLayer(lyr)

        extent = grid.extent()

        exported: list[str] = []
        for theme in themes:
            if not isinstance(theme, dict):
                continue
            name = str(theme.get("name", "theme")).strip()
            title = str(theme.get("title", name)).strip()
            field = str(theme.get("field", "GEOCLAW_IDX")).strip()
            breaks = [float(v) for v in (theme.get("breaks") or [])]
            colors = [str(v) for v in (theme.get("colors") or [])]

            if not name:
                continue

            apply_grid_theme(grid, field, breaks, colors)
            grid.triggerRepaint()

            layout_name = f"{args.layout_prefix}_{name}"
            layout = add_layout(project, layout_name, title, [grid, water, roads, hospitals], extent)

            out_png = output_dir / f"{name}.png"
            export_layout(layout, out_png)
            exported.append(str(out_png))

        if not project.write(str(project_path)):
            raise RuntimeError(f"failed to write project: {project_path}")

        print(f"qgis={Qgis.QGIS_VERSION}")
        print(f"project={project_path}")
        for p in exported:
            print(f"map={p}")

        # TODO: Add optional PDF exports and custom layout sizes per theme.
        # TODO: Add atlas export driven by district boundaries when administrative layer is available.
    finally:
        app.exitQgis()
        if gdal is not None:
            gdal.PopErrorHandler()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
