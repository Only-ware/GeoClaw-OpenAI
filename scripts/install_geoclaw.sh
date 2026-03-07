#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[INFO] install_geoclaw.sh is deprecated. Use scripts/install_geoclaw_openai.sh."
exec "${ROOT_DIR}/scripts/install_geoclaw_openai.sh"
