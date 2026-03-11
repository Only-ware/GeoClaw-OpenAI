# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

## [3.2.3] - 2026-03-11

### Added
- Added lightweight built-in Web trial UI:
  - new CLI command: `geoclaw-openai web --host 127.0.0.1 --port 8765 --open-browser`
  - includes session management (create/switch/delete), error prompt + retry, execution status, and output/report links.
  - page header includes copyright and GitHub repository link for team trial distribution.
- Added `web` module and API surface:
  - `src/geoclaw_qgis/web/app.py`
  - `GET /api/sessions`, `POST /api/sessions`, `GET /api/sessions/{id}`, `DELETE /api/sessions/{id}`
  - `POST /api/chat`, `GET /api/file`, `GET /api/health`
- Added uninstall/reinstall support:
  - new CLI commands: `geoclaw-openai uninstall`, `geoclaw-openai reinstall`
  - supports `--dry-run`, `--yes`, and optional `--purge-home` for config cleanup.
  - added shell wrappers:
    - `scripts/uninstall_geoclaw_openai.sh`
    - `scripts/reinstall_geoclaw_openai.sh`
- Added responsive chat viewport behavior in web UI:
  - chat panel now adapts with browser window size and keeps scrollable content area stable.
  - session list remains independently scrollable under dynamic viewport changes.

### Changed
- Improved chat profile update feedback:
  - natural-language preference updates now return explicit system feedback in `chat.reply`.
  - summary-only profile update now explains why no writable field was recognized and provides examples.
- Improved web chat latest-message follow behavior:
  - auto-scroll keeps view at latest message when pinned to bottom.
  - preserves manual scroll state and re-applies bottom follow on resize.
- Bumped project/package runtime version to `3.2.3`.

### Tested
- `python3 -m unittest discover -s src/geoclaw_qgis/tests -q` (132 tests, pass).
- Manual web smoke:
  - `python3 -m geoclaw_qgis.cli.main web --host 127.0.0.1 --port 8877`
  - validated `/api/health`, `/api/sessions`, responsive resize and latest-message scroll behavior.

## [3.2.2] - 2026-03-10

### Added
- Added 30-round AI chit-chat regression runner:
  - `scripts/run_dialogue_30_chitchat.sh`
- Added full 30-round QA dialogue report:
  - `examples/chat/dialogue_suite_30_rounds_chitchat_full_20260310.md`

### Changed
- Bumped project/package runtime version to `3.2.2`.
- Enforced `chat` mode as AI-required by default:
  - `--no-ai` is disabled for normal usage and hidden from CLI help.
- Updated skill runner to AI-first default:
  - `scripts/geoclaw_skill_runner.py` now enables AI summarization by default;
  - can be disabled per run with `--no-ai`.
- Updated README and user docs to consistently guide AI-first usage.

### Tested
- `python3 -m unittest discover -s src/geoclaw_qgis/tests` (118 tests, pass).
- `bash scripts/run_dialogue_30_chitchat.sh` (PASS=30, FAIL=0, AI mode).

## [3.2.1] - 2026-03-10

### Added
- Added fixed GeoClaw identity definition module:
  - `src/geoclaw_qgis/identity.py`
  - defines what GeoClaw-OpenAI is, who developed it, core capabilities, and reference files.
- Added chat fallback identity answer guardrail for identity questions.
- Added dialogue regression suites:
  - `scripts/run_dialogue_10_rounds.sh`
  - `scripts/run_dialogue_15_rounds.sh`
  - `scripts/run_dialogue_20_rounds.sh`
- Added readable dialogue reports:
  - `examples/chat/dialogue_suite_10_rounds_easy_read_20260310.md`
  - `examples/chat/dialogue_suite_15_rounds_20260310.md`
  - `examples/chat/dialogue_suite_20_rounds_easy_read_20260310.md`

### Changed
- Bumped project/package runtime version to `3.2.1`.
- Updated chat AI system prompt to include fixed identity block and explicit non-Clawpack disambiguation.
- Updated README with dialogue-report references and regression-suite commands.

### Fixed
- Fixed NL routing false positives:
  - avoid substring collision (`od` in words like `introduce`) incorrectly routing to `network`.
  - avoid English pseudo-city extraction from phrases like `previous turn` / `one sentence`.
  - support `check for updates` plural form routing to `update`.
  - prioritize conversational self-introduction/summarization requests to `chat`.
- Fixed skill AI summary report source when pipeline `out_dir` is overridden via `--set out_dir=...`.

### Tested
- `python3 -m unittest discover -s src/geoclaw_qgis/tests` (115 tests, pass).
- Dialogue suite regression:
  - `bash scripts/run_dialogue_10_rounds.sh` (PASS=10, FAIL=0)
  - `bash scripts/run_dialogue_15_rounds.sh` (PASS=15, FAIL=0)
  - `bash scripts/run_dialogue_20_rounds.sh` (PASS=20, FAIL=0)

## [3.2.0] - 2026-03-10

### Added
- Added OpenClaw-style skill import capability:
  - `geoclaw-openai skill-registry import-openclaw`
  - Converts OpenClaw JSON/YAML spec into GeoClaw `pipeline/ai/builtin` skill spec.
  - Reuses existing skill safety assessment + user confirmation flow before registration.
- Added OpenClaw sample spec:
  - `configs/examples/openclaw_skill_example.yaml`
- Added continuous chat mode with persisted sessions:
  - `geoclaw-openai chat --interactive --session-id <id>`
  - single-turn chat can reuse history with `--session-id`.
- Added chat-driven profile evolution + hot reload:
  - chat messages that route to `profile` intent now apply updates immediately
  - `user.md/soul.md` changes are hot-reloaded in current chat session.

### Changed
- Bumped project/package runtime version to `3.2.0`.
- Updated README/docs with OpenClaw import + continuous chat + chat profile hot-reload examples.
- Updated chat flow to support both casual conversation and workflow triggering in one command path.

### Tested
- `python3 -m unittest discover -s src/geoclaw_qgis/tests` (109 tests, pass).
- `python3 -m geoclaw_qgis.cli.main skill-registry import-openclaw --spec-file configs/examples/openclaw_skill_example.yaml --id-prefix oc_ --dry-run` (pass).
- `python3 -m geoclaw_qgis.cli.main chat --interactive --session-id demo_chat --new-session --no-ai` (pass, session persisted).

## [3.1.3] - 2026-03-10

### Added
- Added OpenClaw-style skill import capability:
  - `geoclaw-openai skill-registry import-openclaw`
  - Converts OpenClaw JSON/YAML spec into GeoClaw `pipeline/ai/builtin` skill spec.
  - Reuses existing skill safety assessment + user confirmation flow before registration.
- Added OpenClaw sample spec:
  - `configs/examples/openclaw_skill_example.yaml`

### Changed
- Bumped project/package runtime version to `3.1.3`.
- Updated README/docs with OpenClaw import usage examples.
- Updated CLI parser and skill docs to include `import-openclaw`.

### Tested
- `python3 -m unittest discover -s src/geoclaw_qgis/tests` (105 tests, pass).
- `python3 -m geoclaw_qgis.cli.main skill-registry import-openclaw --spec-file configs/examples/openclaw_skill_example.yaml --id-prefix oc_ --dry-run` (pass).

## [3.1.2] - 2026-03-09

### Added
- Added a beginner-facing analysis-skill quickstart guide:
  - `docs/analysis-skills-quickstart.md`
  - covers ready-to-run `pipeline/ai/builtin` skills, minimal commands, and output locations.

### Changed
- Bumped project/package runtime version to `3.1.2`.
- Updated README quick links and versioned sections for `v3.1.2`.
- Updated docs version headers to `v3.1.2` across onboarding/guide/reference pages.
- Updated skill authoring spec to include `builtin` type requirements and test steps.
- Updated engineering-manual generator text/version to `v3.1.2`.

### Tested
- `python3 -m unittest discover -s src/geoclaw_qgis/tests` (100 tests, pass).
- Skill smoke checks:
  - `python3 scripts/geoclaw_skill_runner.py --list`
  - `python3 scripts/geoclaw_skill_runner.py --skill vector_basics_qgis --set raw_dir=data/raw/wuhan_osm --set out_dir=data/outputs/demo_vector_v312 --skip-download`
  - `python3 scripts/geoclaw_skill_runner.py --skill raster_basics_qgis --set raw_dir=data/raw/wuhan_osm --set out_dir=data/outputs/demo_raster_v312 --skip-download`
  - `python3 scripts/geoclaw_skill_runner.py --skill network_trackintel_skill --args \"--pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv --out-dir data/outputs/network_trackintel_v312\"`

## [3.1.1] - 2026-03-09

### Added
- Added onboarding API key UX enhancements:
  - interactive key input is visible (not hidden) for long-key verification
  - reconfiguration prompt shows masked hint with key prefix/suffix only.
- Added chat execution delegation path:
  - `geoclaw-openai chat --execute` delegates actionable requests to `nl --execute`
  - supports `--use-sre` and `--sre-report-out`.
- Added a new end-to-end user case:
  - `data/examples/chat_mode/jingdezhen_mall_top5/`
  - includes chat process, raw output, reasoning report, and top-5 CSV summary.

### Changed
- Hardened NL routing for mall-like requests with explicit non-Wuhan data sources:
  - preserve explicit `--city/--bbox/--data-dir` and keep native `run` route
  - reject conflicting SRE reroute when source constraints are explicit.
- Enhanced fallback chat behavior with `soul.md/user.md` personalization:
  - language/tone-aware suggestions and replies
  - mission-aware fallback phrasing.
- Updated README/docs and engineering manual to `v3.1.1`.
- Bumped runtime/package version to `3.1.1`.

### Tested
- `python3 -m unittest discover -s src/geoclaw_qgis/tests` (93 tests, pass).
- End-to-end chat scenario (Jingdezhen mall top-5) generated artifacts successfully.

## [3.1.0] - 2026-03-08

### Added
- Added local LLM provider support via Ollama:
  - `GEOCLAW_AI_PROVIDER=ollama`
  - default `GEOCLAW_OLLAMA_BASE_URL=http://127.0.0.1:11434/v1`
  - default `GEOCLAW_OLLAMA_MODEL=llama3.1:8b`
- Added profile evolution command:
  - `geoclaw-openai profile evolve --target user|soul|both ...`
  - supports `--summary`, repeatable `--set KEY=VALUE`, repeatable `--add KEY=V1,V2`.
- Added natural-language intent routing for profile evolution (NL -> `profile evolve`).
- Added tests for:
  - Ollama provider defaults
  - profile dialogue overrides (user updates + soul safety lock)
  - CLI parser for `profile evolve`
  - NL profile intent parsing

### Changed
- Enforced dialogue-level soul safety policy:
  - high-risk safety/execution boundary keys remain blocked from dialogue writes.
- Updated README, technical reference, release notes, and engineering manual for v3.1.0.
- Bumped runtime/package version to `3.1.0`.

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
