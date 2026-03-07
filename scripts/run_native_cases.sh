#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BBOX="${1:-30.50,114.20,30.66,114.45}"

bash "${ROOT_DIR}/scripts/run_location_analysis_case.sh" "${BBOX}"
bash "${ROOT_DIR}/scripts/run_site_selection_case.sh" "${BBOX}"

echo "Native cases done."
echo "Location output: ${ROOT_DIR}/data/outputs/wuhan_location/grid_location.gpkg"
echo "Site output: ${ROOT_DIR}/data/outputs/wuhan_site/site_candidates.gpkg"
