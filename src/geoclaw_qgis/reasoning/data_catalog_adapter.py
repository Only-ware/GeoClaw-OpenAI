from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _extent_overlap(a: list[float], b: list[float]) -> bool:
    if len(a) != 4 or len(b) != 4:
        return False
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _infer_type_from_suffix(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".tif", ".tiff"}:
        return "raster"
    if ext in {".csv"}:
        return "trajectory"
    if ext in {".geojson", ".gpkg", ".shp"}:
        return "vector"
    return "unknown"


def _collect_bbox_from_coords(coords: Any, acc: list[float]) -> None:
    if isinstance(coords, (list, tuple)):
        if len(coords) >= 2 and all(isinstance(x, (int, float)) for x in coords[:2]):
            x, y = float(coords[0]), float(coords[1])
            if not acc:
                acc.extend([x, y, x, y])
            else:
                acc[0] = min(acc[0], x)
                acc[1] = min(acc[1], y)
                acc[2] = max(acc[2], x)
                acc[3] = max(acc[3], y)
            return
        for item in coords:
            _collect_bbox_from_coords(item, acc)


def _read_geojson_metadata(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features") if isinstance(payload, dict) else None
    geometry = ""
    bbox: list[float] = []

    if isinstance(features, list) and features:
        first = features[0] if isinstance(features[0], dict) else {}
        geom = first.get("geometry") if isinstance(first.get("geometry"), dict) else {}
        geometry = str(geom.get("type", "")).strip().lower()

        for item in features[:200]:
            if not isinstance(item, dict):
                continue
            g = item.get("geometry")
            if not isinstance(g, dict):
                continue
            _collect_bbox_from_coords(g.get("coordinates"), bbox)

    if not bbox and isinstance(payload, dict) and isinstance(payload.get("bbox"), list):
        raw = payload.get("bbox")
        try:
            nums = [float(x) for x in raw]
            if len(nums) >= 4:
                bbox = nums[:4]
        except Exception:
            bbox = []

    attrs: list[str] = []
    if isinstance(features, list) and features:
        first = features[0] if isinstance(features[0], dict) else {}
        props = first.get("properties") if isinstance(first.get("properties"), dict) else {}
        attrs = [str(k) for k in props.keys()]

    return {
        "type": "vector",
        "geometry": geometry,
        "extent": bbox,
        "attributes": attrs,
    }


def dataset_spec_from_path(path: Path) -> dict[str, Any]:
    p = path.expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"dataset not found: {p}")

    base = {
        "id": p.stem,
        "path": str(p),
        "type": _infer_type_from_suffix(p),
        "geometry": "",
        "crs": "",
        "extent": [],
        "time_range": "",
        "attributes": [],
        "writable": False,
    }

    if p.suffix.lower() == ".geojson":
        try:
            extra = _read_geojson_metadata(p)
            base.update(extra)
        except Exception:
            pass

    if p.suffix.lower() == ".csv":
        base["type"] = "trajectory"

    return base


def discover_datasets_from_dir(data_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(data_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"data-dir not found: {root}")

    specs: list[dict[str, Any]] = []
    patterns = ["*.geojson", "*.gpkg", "*.shp", "*.tif", "*.tiff", "*.csv"]
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.name.startswith("."):
                continue
            specs.append(dataset_spec_from_path(path))
    return specs


def merge_dataset_specs(
    *,
    base: list[dict[str, Any]] | None = None,
    extra: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for items in [base or [], extra or []]:
        for row in items:
            rid = str(row.get("id", "")).strip()
            if not rid or rid in seen:
                continue
            seen.add(rid)
            merged.append(row)
    return merged


def check_extent_overlaps(datasets: list[dict[str, Any]]) -> bool:
    extents = [x.get("extent") for x in datasets if isinstance(x.get("extent"), list) and len(x.get("extent")) == 4]
    if len(extents) < 2:
        return True
    for i in range(len(extents)):
        for j in range(i + 1, len(extents)):
            a = [float(v) for v in extents[i]]
            b = [float(v) for v in extents[j]]
            if _extent_overlap(a, b):
                return True
    return False
