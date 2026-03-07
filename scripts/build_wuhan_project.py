#!/Applications/QGIS.app/Contents/MacOS/bin/python3
"""Build a QGIS project and layout from Wuhan analysis outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFillSymbol,
    QgsGraduatedSymbolRenderer,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPage,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLineSymbol,
    QgsMapLayer,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsRendererRange,
    QgsSingleSymbolRenderer,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsSymbol,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--analysis-dir", default="data/outputs/wuhan_analysis")
    p.add_argument("--project-path", default="data/outputs/wuhan_analysis/wuhan_analysis.qgz")
    p.add_argument("--layout-name", default="Wuhan_Overview")
    return p.parse_args()


def load_vec(path: Path, name: str) -> QgsVectorLayer:
    layer = QgsVectorLayer(str(path), name, "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Invalid layer: {path}")
    return layer


def apply_grid_style(layer: QgsVectorLayer) -> None:
    field = "GEOCLAW_IDX"
    if layer.fields().indexFromName(field) < 0:
        return

    sym1 = QgsFillSymbol.createSimple({"color": "#f0f9e8", "outline_color": "#aaaaaa", "outline_width": "0.1"})
    sym2 = QgsFillSymbol.createSimple({"color": "#bae4bc", "outline_color": "#888888", "outline_width": "0.1"})
    sym3 = QgsFillSymbol.createSimple({"color": "#7bccc4", "outline_color": "#666666", "outline_width": "0.1"})
    sym4 = QgsFillSymbol.createSimple({"color": "#2b8cbe", "outline_color": "#444444", "outline_width": "0.1"})

    ranges = [
        QgsRendererRange(0, 10, sym1, "0 - 10"),
        QgsRendererRange(10, 20, sym2, "10 - 20"),
        QgsRendererRange(20, 35, sym3, "20 - 35"),
        QgsRendererRange(35, 9999, sym4, "> 35"),
    ]
    renderer = QgsGraduatedSymbolRenderer(field, ranges)
    layer.setRenderer(renderer)


def apply_line_style(layer: QgsVectorLayer, color: str, width: str) -> None:
    symbol = QgsLineSymbol.createSimple({"line_color": color, "line_width": width})
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def apply_point_style(layer: QgsVectorLayer) -> None:
    symbol = QgsSymbol.defaultSymbol(layer.geometryType())
    if symbol is None:
        return
    symbol.setColor(QColor("#d7301f"))
    symbol.setSize(2.2)
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def add_layout(project: QgsProject, layout_name: str, layers: list[QgsMapLayer], extent: QgsRectangle) -> None:
    manager = project.layoutManager()
    existing = manager.layoutByName(layout_name)
    if existing:
        manager.removeLayout(existing)

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(layout_name)

    page = layout.pageCollection().pages()[0]
    page.setPageSize("A4", QgsLayoutItemPage.Orientation.Landscape)  # type: ignore[name-defined]

    map_item = QgsLayoutItemMap(layout)
    map_item.attemptMove(QgsLayoutPoint(10, 20, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(270, 170, QgsUnitTypes.LayoutMillimeters))
    map_item.setExtent(extent)
    map_item.setLayers(layers)
    layout.addLayoutItem(map_item)

    title = QgsLayoutItemLabel(layout)
    title.setText("Wuhan GeoClaw Analysis (OSM Sample)")
    txt_fmt = QgsTextFormat()
    txt_fmt.setFont(QFont("Helvetica", 16))
    title.setTextFormat(txt_fmt)
    title.adjustSizeToText()
    title.attemptMove(QgsLayoutPoint(10, 8, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(title)

    legend = QgsLayoutItemLegend(layout)
    legend.setLinkedMap(map_item)
    legend.attemptMove(QgsLayoutPoint(230, 25, QgsUnitTypes.LayoutMillimeters))
    legend.attemptResize(QgsLayoutSize(45, 80, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(legend)

    manager.addLayout(layout)


def main() -> int:
    args = parse_args()

    prefix = Path("/Applications/QGIS.app/Contents/MacOS")
    QgsApplication.setPrefixPath(str(prefix), True)
    app = QgsApplication([], False)
    app.initQgis()

    try:
        analysis_dir = Path(args.analysis_dir).resolve()
        project_path = Path(args.project_path).resolve()
        project_path.parent.mkdir(parents=True, exist_ok=True)

        grid = load_vec(analysis_dir / "grid_final.gpkg", "Grid Index")
        roads = load_vec(analysis_dir / "roads_32650.gpkg", "Roads")
        water = load_vec(analysis_dir / "water_32650.gpkg", "Water")
        hospitals = load_vec(analysis_dir / "hospitals_32650.gpkg", "Hospitals")

        apply_grid_style(grid)
        apply_line_style(roads, "#4d4d4d", "0.18")
        apply_line_style(water, "#1f78b4", "0.35")
        apply_point_style(hospitals)

        project = QgsProject.instance()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:32650"))
        project.clear()
        project.addMapLayer(grid)
        project.addMapLayer(water)
        project.addMapLayer(roads)
        project.addMapLayer(hospitals)

        root = project.layerTreeRoot()
        root.clear()
        group = root.addGroup("Wuhan Analysis")
        for lyr in [grid, water, roads, hospitals]:
            group.addLayer(lyr)

        extent = grid.extent()
        add_layout(project, args.layout_name, [grid, water, roads, hospitals], extent)

        if not project.write(str(project_path)):
            raise RuntimeError(f"failed to write project: {project_path}")

        print(f"project={project_path}")
        print(f"layout={args.layout_name}")
        print(f"qgis={Qgis.QGIS_VERSION}")
    finally:
        app.exitQgis()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
