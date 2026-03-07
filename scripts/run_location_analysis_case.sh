#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BBOX="${1:-30.50,114.20,30.66,114.45}"
PIPELINE="${2:-${ROOT_DIR}/pipelines/cases/location_analysis.yaml}"

has_local_osm_data() {
  local osm_dir="${ROOT_DIR}/data/raw/wuhan_osm"
  local required=(
    "${osm_dir}/roads.geojson"
    "${osm_dir}/water.geojson"
    "${osm_dir}/hospitals.geojson"
    "${osm_dir}/study_area.geojson"
  )
  local f
  for f in "${required[@]}"; do
    if [ ! -s "${f}" ]; then
      return 1
    fi
  done
  return 0
}

if ! python3 "${ROOT_DIR}/scripts/download_osm_wuhan.py" --bbox "${BBOX}" --timeout 120; then
  if has_local_osm_data; then
    echo "[WARN] OSM 下载失败，使用本地缓存数据继续执行。"
    # TODO: Add optional cache freshness checks to prevent stale-data misuse in production runs.
  else
    echo "[ERROR] OSM 下载失败且不存在可用本地缓存。"
    exit 1
  fi
fi

python3 "${ROOT_DIR}/scripts/run_qgis_pipeline.py" --config "${PIPELINE}"

echo "Location analysis done: ${ROOT_DIR}/data/outputs/wuhan_location/grid_location.gpkg"
