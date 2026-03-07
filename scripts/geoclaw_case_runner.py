#!/usr/bin/env python3
"""Run built-in GeoClaw cases from city name, bbox, or local data folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geoclaw_qgis.config import bootstrap_runtime_env
from geoclaw_qgis.project_info import LAB_AFFILIATION, PROJECT_ATTRIBUTION, PROJECT_VERSION
from geoclaw_qgis.security import fixed_output_root


DEFAULT_BBOX = "30.50,114.20,30.66,114.45"
REQUIRED_RAW_FILES = ("roads.geojson", "water.geojson", "hospitals.geojson", "study_area.geojson")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run GeoClaw native/advanced cases with flexible input source.",
    )
    parser.add_argument(
        "--case",
        default="native_cases",
        choices=["location_analysis", "site_selection", "native_cases", "wuhan_advanced"],
        help="which built-in case to run",
    )

    src = parser.add_mutually_exclusive_group()
    src.add_argument("--city", default="", help="city name for geocoding and OSM download")
    src.add_argument("--bbox", default="", help="south,west,north,east for OSM download")
    src.add_argument("--data-dir", default="", help="local folder with roads/water/hospitals/study_area GeoJSON")

    parser.add_argument("--tag", default="", help="output tag; default inferred from input")
    parser.add_argument("--raw-dir", default="", help="download/cache raw data directory")
    parser.add_argument("--out-root", default="", help="root directory for outputs (fixed by security policy)")
    parser.add_argument("--top-n", type=int, default=12, help="top candidates for site selection")
    parser.add_argument("--timeout", type=int, default=120, help="download timeout seconds")
    parser.add_argument("--skip-download", action="store_true", help="never download OSM; require local raw files")
    parser.add_argument("--force-download", action="store_true", help="force refresh OSM download")
    parser.add_argument("--with-maps", action="store_true", help="export thematic maps")
    parser.add_argument("--no-maps", action="store_true", help="skip thematic map export")
    parser.add_argument("--qgis-python", default="", help="explicit QGIS python path for map export")
    return parser.parse_args()


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text.strip())
    cleaned = cleaned.strip("_").lower()
    return cleaned or "custom"


def bbox_tag(bbox: str) -> str:
    digest = hashlib.sha1(bbox.encode("utf-8")).hexdigest()[:8]
    return f"bbox_{digest}"


def has_raw_data(data_dir: Path) -> bool:
    return all((data_dir / name).is_file() and (data_dir / name).stat().st_size > 0 for name in REQUIRED_RAW_FILES)


def ensure_raw_data(data_dir: Path) -> None:
    missing = [name for name in REQUIRED_RAW_FILES if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"raw data dir missing files: {missing}. expected {list(REQUIRED_RAW_FILES)} in {data_dir}"
        )


def run_cmd(cmd: list[str]) -> None:
    print("[RUN] " + shlex.join(cmd), flush=True)
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def pick_qgis_python(explicit: str = "") -> str:
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists() and p.is_file():
            return str(p.resolve())
        raise FileNotFoundError(f"qgis python not found: {explicit}")

    env_qp = os.environ.get("GEOCLAW_OPENAI_QGIS_PROCESS", "").strip()
    if env_qp:
        qp = Path(env_qp).expanduser()
        candidate = qp.parent / "python3"
        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())

    candidates = [
        "/Applications/QGIS.app/Contents/MacOS/bin/python3",
        "/Applications/QGIS-LTR.app/Contents/MacOS/bin/python3",
    ]
    for candidate in candidates:
        p = Path(candidate)
        if p.exists() and p.is_file():
            return str(p.resolve())
    raise FileNotFoundError("QGIS python not found; set --qgis-python or install QGIS desktop")


def resolve_tag(args: argparse.Namespace) -> str:
    if args.tag:
        return slugify(args.tag)
    if args.city:
        return slugify(args.city)
    if args.bbox:
        return bbox_tag(args.bbox)
    if args.data_dir:
        return slugify(Path(args.data_dir).name)
    return "wuhan"


def resolve_user_path(path_text: str) -> Path:
    return Path(path_text).expanduser().resolve()


def prepare_raw_data(args: argparse.Namespace, tag: str) -> tuple[Path, str]:
    if args.data_dir:
        raw_dir = resolve_user_path(args.data_dir)
        ensure_raw_data(raw_dir)
        print(f"[GUIDE] input_mode=local_data raw_dir={raw_dir}", flush=True)
        return raw_dir, ""

    if args.raw_dir:
        raw_dir = resolve_user_path(args.raw_dir)
    elif tag == "wuhan":
        raw_dir = (ROOT / "data/raw/wuhan_osm").resolve()
    else:
        raw_dir = (ROOT / f"data/raw/{tag}_osm").resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)

    chosen_bbox = args.bbox.strip() or os.environ.get("GEOCLAW_OPENAI_DEFAULT_BBOX", "").strip() or DEFAULT_BBOX
    use_city = args.city.strip()

    if args.skip_download and not has_raw_data(raw_dir):
        raise RuntimeError(f"--skip-download is set but raw data is incomplete in {raw_dir}")

    need_download = args.force_download or not has_raw_data(raw_dir)
    if need_download and not args.skip_download:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "download_osm_wuhan.py"),
            "--output-dir",
            str(raw_dir),
            "--timeout",
            str(args.timeout),
        ]
        if use_city:
            cmd.extend(["--city", use_city])
            print(f"[GUIDE] input_mode=city city={use_city}", flush=True)
        else:
            cmd.extend(["--bbox", chosen_bbox])
            print(f"[GUIDE] input_mode=bbox bbox={chosen_bbox}", flush=True)
        run_cmd(cmd)
    else:
        if use_city:
            print(f"[GUIDE] input_mode=city (cached) city={use_city}", flush=True)
        else:
            print(f"[GUIDE] input_mode=bbox (cached) bbox={chosen_bbox}", flush=True)

    ensure_raw_data(raw_dir)
    return raw_dir, chosen_bbox


def run_pipeline(config_path: Path, overrides: dict[str, str]) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / "run_qgis_pipeline.py"), "--config", str(config_path)]
    for key, value in overrides.items():
        cmd.extend(["--set", f"{key}={value}"])
    run_cmd(cmd)


def export_maps(analysis_dir: Path, tag: str, qgis_python: str) -> None:
    cmd = [
        qgis_python,
        str(ROOT / "scripts" / "export_thematic_maps.py"),
        "--analysis-dir",
        str(analysis_dir),
        "--themes",
        str(ROOT / "configs" / "thematic_maps.yaml"),
        "--output-dir",
        str(analysis_dir / "maps"),
        "--project-path",
        str(analysis_dir / "thematic_maps.qgz"),
        "--layout-prefix",
        tag,
    ]
    run_cmd(cmd)


def main() -> int:
    bootstrap_runtime_env()
    args = parse_args()
    tag = resolve_tag(args)
    raw_dir, chosen_bbox = prepare_raw_data(args, tag)

    secure_out_root = fixed_output_root(ROOT)
    requested_out_root = resolve_user_path(args.out_root) if args.out_root else secure_out_root
    if requested_out_root != secure_out_root:
        raise ValueError(
            f"Unsafe --out-root: {requested_out_root}. "
            f"GeoClaw security policy requires fixed output root: {secure_out_root}"
        )
    out_root = secure_out_root
    out_root.mkdir(parents=True, exist_ok=True)

    location_out = (out_root / f"{tag}_location").resolve()
    site_out = (out_root / f"{tag}_site").resolve()
    advanced_out = (out_root / f"{tag}_analysis").resolve()
    location_out.mkdir(parents=True, exist_ok=True)
    site_out.mkdir(parents=True, exist_ok=True)
    advanced_out.mkdir(parents=True, exist_ok=True)

    if args.with_maps and args.no_maps:
        raise ValueError("--with-maps and --no-maps cannot be used together")
    run_maps = args.with_maps or (args.case == "wuhan_advanced" and not args.no_maps)

    location_cfg = ROOT / "pipelines/cases/location_analysis.yaml"
    site_cfg = ROOT / "pipelines/cases/site_selection.yaml"
    advanced_cfg = ROOT / "pipelines/wuhan_geoclaw.yaml"

    results: dict[str, Any] = {
        "version": PROJECT_VERSION,
        "attribution": PROJECT_ATTRIBUTION,
        "lab_affiliation": LAB_AFFILIATION,
        "case": args.case,
        "tag": tag,
        "raw_dir": str(raw_dir),
        "out_root": str(out_root),
        "bbox": chosen_bbox,
    }

    if args.case in {"location_analysis", "native_cases", "site_selection"}:
        run_pipeline(
            location_cfg,
            {
                "raw_dir": str(raw_dir),
                "out_dir": str(location_out),
            },
        )
        results["location_output"] = str(location_out / "grid_location.gpkg")

    if args.case in {"site_selection", "native_cases"}:
        # TODO: Support custom file-name mapping instead of fixed grid_location.gpkg dependency.
        run_pipeline(
            site_cfg,
            {
                "location_input": str(location_out / "grid_location.gpkg"),
                "out_dir": str(site_out),
                "top_n": str(args.top_n),
            },
        )
        results["site_output"] = str(site_out / "site_candidates.gpkg")

    if args.case == "wuhan_advanced":
        run_pipeline(
            advanced_cfg,
            {
                "raw_dir": str(raw_dir),
                "out_dir": str(advanced_out),
            },
        )
        results["advanced_output"] = str(advanced_out / "grid_clustered.gpkg")
        if run_maps:
            qgis_python = pick_qgis_python(args.qgis_python)
            export_maps(advanced_out, tag, qgis_python)
            results["maps_dir"] = str(advanced_out / "maps")

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("[GUIDE] 完成后可直接使用输出 GPKG 在 QGIS 中加载分析字段进行复核。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
