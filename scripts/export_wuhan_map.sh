#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ANALYSIS_DIR="${ROOT_DIR}/data/outputs/wuhan_analysis"

/Applications/QGIS.app/Contents/MacOS/bin/python3 "${ROOT_DIR}/scripts/export_thematic_maps.py" \
  --analysis-dir "${ANALYSIS_DIR}" \
  --themes "${ROOT_DIR}/configs/thematic_maps.yaml" \
  --output-dir "${ANALYSIS_DIR}/maps" \
  --project-path "${ANALYSIS_DIR}/thematic_maps.qgz" \
  --layout-prefix "Wuhan"
