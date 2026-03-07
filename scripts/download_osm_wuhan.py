#!/usr/bin/env python3
"""Download OSM sample data from Overpass API and export GeoJSON layers."""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_BBOX = "30.45,114.10,30.72,114.52"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download OSM test data by city name or bbox")
    parser.add_argument(
        "--city",
        default="",
        help="optional city name for geocoding to bbox (e.g. Wuhan, China)",
    )
    parser.add_argument(
        "--bbox",
        default="",
        help="south,west,north,east in EPSG:4326",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw/wuhan_osm",
        help="output directory for generated GeoJSON files",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Overpass timeout seconds",
    )
    parser.add_argument(
        "--endpoint",
        default="",
        help="optional custom Overpass endpoint",
    )
    parser.add_argument(
        "--geocode-endpoint",
        default="https://nominatim.openstreetmap.org/search",
        help="Nominatim geocoding endpoint",
    )
    return parser.parse_args()


def bbox_tuple(raw: str) -> tuple[float, float, float, float]:
    parts = [float(x.strip()) for x in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must have 4 comma-separated numbers")
    south, west, north, east = parts
    if south >= north or west >= east:
        raise ValueError("bbox order must satisfy south<north and west<east")
    return south, west, north, east


def overpass_query(query: str, timeout: int, endpoint: str = "") -> dict[str, Any]:
    data = query.encode("utf-8")
    endpoints = [endpoint] if endpoint else list(OVERPASS_ENDPOINTS)
    last_err: Exception | None = None

    for ep in endpoints:
        req = urllib.request.Request(
            ep,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        )
        for i in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout + 30) as resp:
                    payload = resp.read().decode("utf-8")
                    return json.loads(payload)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                last_err = exc
                time.sleep(2 + i * 2)
    raise RuntimeError(f"Overpass request failed after retries: {last_err}")


def geocode_city_bbox(city: str, timeout: int, endpoint: str) -> tuple[tuple[float, float, float, float], str]:
    params = {
        "q": city,
        "format": "jsonv2",
        "limit": "1",
    }
    url = endpoint.rstrip("?") + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "geoclaw-openai/0.1 (research-gis-tool)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout + 20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"city geocoding failed for '{city}': {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"city geocoding returned no results for '{city}'")

    item = payload[0]
    raw_bbox = item.get("boundingbox") or []
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        raise RuntimeError(f"invalid geocode bbox for '{city}': {item}")

    south = float(raw_bbox[0])
    north = float(raw_bbox[1])
    west = float(raw_bbox[2])
    east = float(raw_bbox[3])
    return (south, west, north, east), str(item.get("display_name", city))


def make_fc(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def feature(geom_type: str, coords: Any, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": geom_type, "coordinates": coords},
    }


def is_closed(coords: list[tuple[float, float]]) -> bool:
    if len(coords) < 4:
        return False
    return math.isclose(coords[0][0], coords[-1][0]) and math.isclose(coords[0][1], coords[-1][1])


def extract_roads(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in elements:
        if e.get("type") != "way":
            continue
        tags = e.get("tags") or {}
        highway = tags.get("highway")
        geom = e.get("geometry") or []
        if not highway or len(geom) < 2:
            continue

        coords = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
        if len(coords) < 2:
            continue

        out.append(
            feature(
                "LineString",
                coords,
                {
                    "osm_id": e.get("id"),
                    "highway": highway,
                    "name": tags.get("name", ""),
                    "surface": tags.get("surface", ""),
                },
            )
        )
    return out


def extract_water(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in elements:
        if e.get("type") != "way":
            continue
        tags = e.get("tags") or {}
        geom = e.get("geometry") or []
        waterway = tags.get("waterway")
        natural = tags.get("natural")
        landuse = tags.get("landuse")

        if not (waterway or natural == "water" or landuse == "reservoir"):
            continue

        coords = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
        if len(coords) < 2:
            continue

        props = {
            "osm_id": e.get("id"),
            "waterway": waterway or "",
            "natural": natural or "",
            "landuse": landuse or "",
            "name": tags.get("name", ""),
        }

        if (natural == "water" or landuse == "reservoir") and is_closed(coords):
            out.append(feature("Polygon", [coords], props))
        else:
            out.append(feature("LineString", coords, props))
    return out


def polygon_centroid(coords: list[tuple[float, float]]) -> tuple[float, float]:
    # simple arithmetic centroid for small footprint features
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def extract_hospitals(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in elements:
        tags = e.get("tags") or {}
        amenity = tags.get("amenity", "")
        if amenity not in {"hospital", "clinic"}:
            continue

        if e.get("type") == "node" and "lon" in e and "lat" in e:
            out.append(
                feature(
                    "Point",
                    [e["lon"], e["lat"]],
                    {
                        "osm_id": e.get("id"),
                        "amenity": amenity,
                        "name": tags.get("name", ""),
                    },
                )
            )
        elif e.get("type") == "way":
            geom = e.get("geometry") or []
            coords = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
            if len(coords) >= 3:
                cx, cy = polygon_centroid(coords)
                out.append(
                    feature(
                        "Point",
                        [cx, cy],
                        {
                            "osm_id": e.get("id"),
                            "amenity": amenity,
                            "name": tags.get("name", ""),
                        },
                    )
                )
    return out


def write_geojson(path: Path, fc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")


def run_layer_query(
    bbox: tuple[float, float, float, float], timeout: int, layer: str, endpoint: str = ""
) -> list[dict[str, Any]]:
    south, west, north, east = bbox
    if layer == "roads":
        body = f"way[\"highway\"]({south},{west},{north},{east});"
    elif layer == "water":
        body = (
            f"way[\"waterway\"]({south},{west},{north},{east});"
            f"way[\"natural\"=\"water\"]({south},{west},{north},{east});"
            f"way[\"landuse\"=\"reservoir\"]({south},{west},{north},{east});"
        )
    elif layer == "hospitals":
        body = (
            f"node[\"amenity\"~\"hospital|clinic\"]({south},{west},{north},{east});"
            f"way[\"amenity\"~\"hospital|clinic\"]({south},{west},{north},{east});"
        )
    else:
        raise ValueError(f"unsupported layer {layer}")

    query = f"[out:json][timeout:{timeout}];({body});out body qt geom;"
    payload = overpass_query(query, timeout=timeout, endpoint=endpoint)
    return payload.get("elements", [])


def study_area_feature(bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    south, west, north, east = bbox
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return feature(
        "Polygon",
        [ring],
        {
            "name": "wuhan_study_area",
            "south": south,
            "west": west,
            "north": north,
            "east": east,
        },
    )


def main() -> int:
    args = parse_args()
    display_name = ""
    if args.city:
        if args.bbox:
            # TODO: Add explicit mode flags to avoid ambiguous city+bbox inputs.
            print("[WARN] --city and --bbox both provided; using --bbox.")
            bbox = bbox_tuple(args.bbox)
        else:
            bbox, display_name = geocode_city_bbox(args.city, args.timeout, args.geocode_endpoint)
    else:
        bbox = bbox_tuple(args.bbox or DEFAULT_BBOX)
    out_dir = Path(args.output_dir)

    roads_elements = run_layer_query(bbox, args.timeout, "roads", endpoint=args.endpoint)
    water_elements = run_layer_query(bbox, args.timeout, "water", endpoint=args.endpoint)
    hosp_elements = run_layer_query(bbox, args.timeout, "hospitals", endpoint=args.endpoint)

    roads = extract_roads(roads_elements)
    water = extract_water(water_elements)
    hospitals = extract_hospitals(hosp_elements)
    study_area = [study_area_feature(bbox)]

    write_geojson(out_dir / "roads.geojson", make_fc(roads))
    write_geojson(out_dir / "water.geojson", make_fc(water))
    write_geojson(out_dir / "hospitals.geojson", make_fc(hospitals))
    write_geojson(out_dir / "study_area.geojson", make_fc(study_area))

    print(json.dumps({
        "output_dir": str(out_dir),
        "roads": len(roads),
        "water": len(water),
        "hospitals": len(hospitals),
        "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "city": args.city,
        "city_display_name": display_name,
        "endpoint": args.endpoint or OVERPASS_URL,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
