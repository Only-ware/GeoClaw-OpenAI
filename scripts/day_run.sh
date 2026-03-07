#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
BBOX="${1:-30.50,114.20,30.66,114.45}"

DEFAULT_OPENAI_KEY="${GEOCLAW_OPENAI_API_KEY:-test-key-for-day-run}"
QGIS_BIN="${GEOCLAW_OPENAI_QGIS_PROCESS:-}"
if [ -z "${QGIS_BIN}" ]; then
  if [ -x "/Applications/QGIS.app/Contents/MacOS/bin/qgis_process" ]; then
    QGIS_BIN="/Applications/QGIS.app/Contents/MacOS/bin/qgis_process"
  elif [ -x "/Applications/QGIS-LTR.app/Contents/MacOS/bin/qgis_process" ]; then
    QGIS_BIN="/Applications/QGIS-LTR.app/Contents/MacOS/bin/qgis_process"
  elif command -v qgis_process >/dev/null 2>&1; then
    QGIS_BIN="$(command -v qgis_process)"
  fi
fi

cd "${ROOT_DIR}"

echo "[DAY-RUN] 1/8 install geoclaw-openai"
bash scripts/install_geoclaw_openai.sh

USER_BIN="$(${PYTHON_BIN} - <<'PY'
import site
print(site.USER_BASE + '/bin')
PY
)"
CLI_BIN="${USER_BIN}/geoclaw-openai"
if [ ! -x "${CLI_BIN}" ] && command -v geoclaw-openai >/dev/null 2>&1; then
  CLI_BIN="$(command -v geoclaw-openai)"
fi
if [ ! -x "${CLI_BIN}" ]; then
  echo "[DAY-RUN][ERROR] geoclaw-openai binary not found."
  exit 1
fi

echo "[DAY-RUN] 2/8 onboard runtime"
onboard_cmd=(
  "${CLI_BIN}" onboard
  --non-interactive
  --api-key "${DEFAULT_OPENAI_KEY}"
  --ai-base-url "${GEOCLAW_OPENAI_BASE_URL:-https://api.openai.com/v1}"
  --ai-model "${GEOCLAW_OPENAI_MODEL:-gpt-4.1-mini}"
  --default-bbox "${BBOX}"
  --registry "${GEOCLAW_OPENAI_SKILL_REGISTRY:-configs/skills_registry.json}"
  --workspace "${ROOT_DIR}"
)
if [ -n "${QGIS_BIN}" ]; then
  onboard_cmd+=(--qgis-process "${QGIS_BIN}")
fi
"${onboard_cmd[@]}"

if [ -f "${HOME}/.geoclaw-openai/env.sh" ]; then
  # shellcheck disable=SC1090
  source "${HOME}/.geoclaw-openai/env.sh"
fi

echo "[DAY-RUN] 3/8 skill registry"
"${CLI_BIN}" skill -- --list

echo "[DAY-RUN] 4/8 native cases"
bash scripts/run_native_cases.sh "${BBOX}"

echo "[DAY-RUN] 5/8 wuhan advanced case + maps"
bash scripts/run_wuhan_case.sh "${BBOX}"

echo "[DAY-RUN] 6/8 skill: location_analysis"
"${CLI_BIN}" skill -- --skill location_analysis --skip-download

echo "[DAY-RUN] 7/8 skill: site_selection + ai summary"
"${CLI_BIN}" skill -- --skill site_selection --skip-download --with-ai --ai-input "day-run smoke check"

echo "[DAY-RUN] 8/8 validate key outputs"
for f in \
  "data/raw/wuhan_osm/study_area.geojson" \
  "data/outputs/wuhan_location/grid_location.gpkg" \
  "data/outputs/wuhan_site/site_candidates.gpkg" \
  "data/outputs/wuhan_analysis/grid_clustered.gpkg" \
  "data/outputs/wuhan_analysis/maps/geoclaw_index.png"; do
  if [ ! -f "${f}" ]; then
    echo "[DAY-RUN][ERROR] missing output: ${f}"
    exit 1
  fi
done

echo "[DAY-RUN] success"
