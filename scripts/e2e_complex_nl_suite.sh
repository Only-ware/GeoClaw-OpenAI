#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

cd "${ROOT_DIR}"

run_cli() {
  "${PYTHON_BIN}" -m geoclaw_qgis.cli.main "$@"
}

echo "[E2E] 1/4 mall site selection top-7 + SRE report"
run_cli nl \
  "请在武汉主城区做商场选址，给出前7个候选点，输出推理报告并保持可复现" \
  --use-sre \
  --sre-reasoner-mode deterministic \
  --sre-report-out data/outputs/reasoning/e2e_mall_top7_report.md \
  --execute

ogrinfo -ro data/outputs/mall_site_qgis/mall_candidates.gpkg \
  -sql "SELECT COUNT(*) AS cnt, MIN(MALL_RANK) AS min_rank, MAX(MALL_RANK) AS max_rank FROM mall_candidates" \
  | rg "cnt \(Integer\) = 7" >/dev/null

echo "[E2E] 2/4 local data-dir location analysis + map intent + SRE report"
run_cli nl \
  "请基于本地数据目录 data/raw/wuhan_osm 做区位分析，前15个并出图，要求可复现" \
  --use-sre \
  --sre-reasoner-mode deterministic \
  --sre-report-out data/outputs/reasoning/e2e_location_top15_report.md \
  --execute

test -f data/outputs/wuhan_osm_location/grid_location.gpkg
test -f data/outputs/reasoning/e2e_location_top15_report.md

echo "[E2E] 3/4 trajectory network with explicit out-dir + SRE report"
run_cli nl \
  "请基于 data/examples/trajectory/trackintel_demo_pfs.csv 做复杂网络分析，并输出到 data/outputs/network_e2e_case" \
  --use-sre \
  --sre-reasoner-mode deterministic \
  --sre-report-out data/outputs/reasoning/e2e_network_report.md \
  --execute

for f in \
  data/outputs/network_e2e_case/od_edges.csv \
  data/outputs/network_e2e_case/od_nodes.csv \
  data/outputs/network_e2e_case/od_trips.csv \
  data/outputs/network_e2e_case/network_summary.json; do
  test -f "${f}"
done

echo "[E2E] 4/4 operator buffer with explicit output path"
run_cli nl \
  "请对 data/raw/wuhan_osm/hospitals.geojson 做 800m buffer，输出到 data/outputs/e2e_operator/hosp_buffer_800.gpkg" \
  --use-sre \
  --sre-reasoner-mode deterministic \
  --execute

test -f data/outputs/e2e_operator/hosp_buffer_800.gpkg

echo "[E2E] success"
