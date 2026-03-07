#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RAW_DIR="${1:-${ROOT_DIR}/data/raw/wuhan_osm}"
BBOX="${2:-30.50,114.20,30.66,114.45}"

if [ ! -f "${RAW_DIR}/roads.geojson" ] || [ ! -f "${RAW_DIR}/water.geojson" ] || [ ! -f "${RAW_DIR}/hospitals.geojson" ] || [ ! -f "${RAW_DIR}/study_area.geojson" ]; then
  echo "[INFO] Raw data not complete, downloading by bbox: ${BBOX}"
  python3 "${ROOT_DIR}/scripts/download_osm_wuhan.py" --bbox "${BBOX}" --output-dir "${RAW_DIR}" --timeout 120
fi

python3 "${ROOT_DIR}/scripts/run_qgis_pipeline.py" \
  --config "${ROOT_DIR}/pipelines/examples/vector_basics.yaml" \
  --set "raw_dir=${RAW_DIR}" \
  --set "out_dir=${ROOT_DIR}/data/outputs/demo_vector"

python3 "${ROOT_DIR}/scripts/run_qgis_pipeline.py" \
  --config "${ROOT_DIR}/pipelines/examples/raster_basics.yaml" \
  --set "raw_dir=${RAW_DIR}" \
  --set "out_dir=${ROOT_DIR}/data/outputs/demo_raster"

echo "Beginner demos done."
echo "Vector output: ${ROOT_DIR}/data/outputs/demo_vector/roads_service_corridor.gpkg"
echo "Raster output: ${ROOT_DIR}/data/outputs/demo_raster/grid_heat_norm.gpkg"

# TODO: Add city-name mode in this script by directly passing --city into downloader.
