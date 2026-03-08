#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "${ROOT_DIR}"

if command -v geoclaw-openai >/dev/null 2>&1; then
  geoclaw-openai nl "武汉最适合建商场的前5个地点，输出结果和简要解释" \
    --use-sre \
    --sre-reasoner-mode deterministic \
    --sre-report-out data/outputs/reasoning/wuhan_mall_top5_report.md \
    --execute
else
  python3 -m geoclaw_qgis.cli.main nl "武汉最适合建商场的前5个地点，输出结果和简要解释" \
    --use-sre \
    --sre-reasoner-mode deterministic \
    --sre-report-out data/outputs/reasoning/wuhan_mall_top5_report.md \
    --execute
fi
