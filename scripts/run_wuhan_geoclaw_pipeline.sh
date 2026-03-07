#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_PATH="${1:-${ROOT_DIR}/pipelines/wuhan_geoclaw.yaml}"

python3 "${ROOT_DIR}/scripts/run_qgis_pipeline.py" --config "${CONFIG_PATH}"
