#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

export COPYFILE_DISABLE=1
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

cd "${ROOT_DIR}"
"${PYTHON_BIN}" -m geoclaw_qgis.cli.main reinstall --yes "$@"
