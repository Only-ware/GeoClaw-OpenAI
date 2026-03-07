#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BBOX="${1:-30.50,114.20,30.66,114.45}"
PIPELINE_CONFIG="${2:-${ROOT_DIR}/pipelines/wuhan_geoclaw.yaml}"
FORCE_DOWNLOAD="${FORCE_DOWNLOAD:-0}"

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

if [ "${FORCE_DOWNLOAD}" = "1" ] || ! has_local_osm_data; then
  if ! python3 "${ROOT_DIR}/scripts/download_osm_wuhan.py" --bbox "${BBOX}" --timeout 120; then
    if has_local_osm_data; then
      echo "[WARN] OSM 下载失败，使用本地缓存数据继续执行。"
      # TODO: Add cache version metadata and bbox consistency checks.
    else
      echo "[ERROR] OSM 下载失败且不存在可用本地缓存。"
      exit 1
    fi
  fi
else
  echo "[INFO] 检测到本地 OSM 缓存，跳过下载。设置 FORCE_DOWNLOAD=1 可强制刷新。"
fi

bash "${ROOT_DIR}/scripts/run_wuhan_geoclaw_pipeline.sh" "${PIPELINE_CONFIG}"
bash "${ROOT_DIR}/scripts/export_wuhan_map.sh"

echo "Done. Thematic maps are in: ${ROOT_DIR}/data/outputs/wuhan_analysis/maps"
