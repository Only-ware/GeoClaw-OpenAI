#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "${HOME}/.geoclaw-openai/env.sh" ]; then
  # shellcheck disable=SC1090
  source "${HOME}/.geoclaw-openai/env.sh"
fi

if ! command -v geoclaw-openai >/dev/null 2>&1; then
  echo "[ERROR] geoclaw-openai command not found. Run scripts/install_geoclaw_openai.sh first."
  exit 1
fi

INPUT_CSV="${ROOT_DIR}/data/examples/trajectory/trackintel_demo_pfs.csv"
OUT_DIR="${ROOT_DIR}/data/examples/trajectory/results/network_trackintel_demo"

echo "[DEMO] trackintel complex network analysis"
echo "[DEMO] input=${INPUT_CSV}"
echo "[DEMO] out=${OUT_DIR}"

geoclaw-openai network \
  --pfs-csv "${INPUT_CSV}" \
  --out-dir "${OUT_DIR}" \
  --staypoint-dist-threshold 120 \
  --staypoint-time-threshold 4 \
  --gap-threshold 15 \
  --activity-time-threshold 5 \
  --location-epsilon 80 \
  --location-min-samples 1 \
  --location-agg-level dataset

echo "[DEMO] done"
