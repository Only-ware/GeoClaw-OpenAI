# Changelog

All notable changes to this project are documented in this file.

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
