# Changelog

All notable changes to this project are documented in this file.

## [3.0.0-maintenance] - 2026-03-08

### Added
- Added complex NL end-to-end regression suite:
  - `scripts/e2e_complex_nl_suite.sh`
  - Covers mall site-selection, local data-dir location analysis, trajectory network, and operator parameter-preservation scenarios.

### Changed
- Updated NL routing constraints for generic safety and parameter preservation:
  - `run` intent now only allows SRE reroute to `run/skill`.
  - Preserves explicit NL parameters after SRE routing for `run`, `network`, and `operator` intents.
- Updated `.gitignore` to stop ignoring `data/` so learning datasets/examples remain trackable.
- Updated README/docs and regenerated engineering manual docx/pdf for the maintenance cycle.

## [3.0.0] - 2026-03-08

### Added
- Added NL end-to-end SRE report output options:
  - `geoclaw-openai nl ... --sre-report-out <path>`
  - `geoclaw-openai nl ... --sre-print-report`
- Added NL SRE report tests in:
  - `src/geoclaw_qgis/tests/test_nl_sre_routing.py`

### Changed
- Bumped project/package runtime version to `3.0.0`.
- Closed SRE 3.0 internal milestones (A-F) with hardened runtime and docs convergence.
- Expanded `scripts/day_run.sh` to an 11-step matrix covering:
  - `run + skill + reasoning + nl(use-sre) + memory`
- Updated README/docs and regenerated engineering manual docx/pdf for v3.0.0.

## [2.4.0] - 2026-03-08

### Added
- Added dual profile layers:
  - `soul.md` (system identity, geospatial principles, execution boundaries)
  - `user.md` (user long-term preferences and workflow habits)
- Added profile loader/parser module `src/geoclaw_qgis/profile/layers.py`.
- Added CLI commands:
  - `geoclaw-openai profile init`
  - `geoclaw-openai profile show`
- Added tests for profile parsing and NL integration:
  - `src/geoclaw_qgis/tests/test_profile_layers.py`

### Changed
- Bumped project/package runtime version to `2.4.0`.
- Planner now consumes profile context (`parse_nl_query(..., session=...)`).
- Tool router now consumes profile context in NL execution and skill runner output metadata.
- Pipeline report generator now writes profile-layer metadata into `pipeline_report.json`.
- Memory manager now stores `profile_snapshot` and uses profile hints in auto-review outputs.
- Updated README/docs and regenerated engineering manual docx/pdf for v2.4.0.

## [2.3.4] - 2026-03-08

### Added
- Added mall site-selection Skill examples in two styles:
  - `mall_site_selection_llm` (LLM reasoning style)
  - `mall_site_selection_qgis` (QGIS Processing reproducible style)
- Added Skill security assessment guard and high-risk injection simulation examples.
- Added Skill authoring specification and case documentation for team onboarding.

### Changed
- Bumped project version to `2.3.4`.
- Updated README usage notes for mall-site Skill, pre-registration security assessment, and Skill authoring docs.
- Refreshed engineering manual outputs (`GeoClaw-OpenAI_工程说明书.docx` and PDF companion) for the current version.

## [2.3.3] - 2026-03-07

### Changed
- Bumped project version to `2.3.3`.
- Updated README and docs model examples/lists to latest model families (GPT-5, Gemini 3.x, Qwen3 series).
- Synchronized CLI default model presets and day-run defaults with latest naming.

## [2.1.0] - 2026-03-07

### Added
- Added trajectory test-data module under `data/examples/trajectory/`.
- Added demo dataset `data/examples/trajectory/trackintel_demo_pfs.csv`.
- Added reproducible demo outputs under `data/examples/trajectory/results/network_trackintel_demo/`:
  - `od_edges.csv`
  - `od_nodes.csv`
  - `od_trips.csv`
  - `network_summary.json`

### Changed
- Upgraded project/package version to `2.1.0`.
- Updated CLI/docs/examples to use the trajectory data folder for `network` demo.
- Updated README to include trajectory-processing capability and demo outcomes.

### Notes
- The trajectory-processing algorithm chain is based on Track-Intel by MIE Lab:
  [https://github.com/mie-lab/trackintel](https://github.com/mie-lab/trackintel)

## [2.0.0] - 2026-03-07

### Added
- Natural-language command entry (`geoclaw-openai nl`).
- Memory lifecycle (short-term + long-term review).
- Self-update command (`geoclaw-openai update`).
