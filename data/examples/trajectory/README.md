# Trajectory Demo Data (v2.1.0)

This folder stores trajectory-module demo data and reproducible outputs for `geoclaw-openai network`.

## Files

- `trackintel_demo_pfs.csv`: positionfixes test data.
- `results/network_trackintel_demo/od_edges.csv`: OD edge statistics.
- `results/network_trackintel_demo/od_nodes.csv`: node-level network metrics.
- `results/network_trackintel_demo/od_trips.csv`: trip-level OD mapping.
- `results/network_trackintel_demo/network_summary.json`: run metadata and counts.

## Source Attribution

Trajectory preprocessing and OD graph construction workflow is based on
Track-Intel by MIE Lab: <https://github.com/mie-lab/trackintel>

## Reproduce

```bash
bash scripts/run_trackintel_network_demo.sh
```
