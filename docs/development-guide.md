# GeoClaw-OpenAI 开发指南（v3.2.0）

本文档用于后续开发与维护，重点说明工程结构、核心机制、扩展入口与本地验证流程。

机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 开发目标

GeoClaw-OpenAI 以 `qgis_process` 为执行核心，目标是构建可复现、可扩展、可维护的 GIS + AI 工具链：

- 原生支持区位分析与选址分析
- 支持城市名 / bbox / 本地目录三类输入
- 支持矢量/栅格分析与单算法灵活参数
- 支持 Skill 扩展、自然语言入口与 memory 闭环
- 支持 TrackIntel 轨迹网络分析
- 默认安全输出策略，避免输入数据被覆盖

## 2. 核心目录结构

```text
AI-Agents/
├── configs/
│   ├── skills_registry.json
│   ├── thematic_maps.yaml
│   └── examples/
├── docs/
├── soul.md
├── user.md
├── pipelines/
│   ├── cases/
│   │   ├── location_analysis.yaml
│   │   └── site_selection.yaml
│   ├── examples/
│   └── wuhan_geoclaw.yaml
├── scripts/
│   ├── geoclaw_case_runner.py
│   ├── geoclaw_operator_runner.py
│   ├── geoclaw_skill_runner.py
│   ├── run_qgis_pipeline.py
│   ├── run_trackintel_network_demo.sh
│   └── day_run.sh
├── src/geoclaw_qgis/
│   ├── cli/main.py
│   ├── ai/
│   ├── analysis/
│   ├── memory/
│   ├── nl/
│   ├── profile/
│   ├── security/
│   └── providers/
└── data/
    ├── raw/
    ├── outputs/
    └── examples/trajectory/
```

## 3. 关键模块职责

- `cli/main.py`
  - 命令入口：`onboard/config/env/update/run/operator/network/skill/profile/memory/nl`
  - 除 `memory` 命令外，自动记录短期 memory 并自动复盘到长期 memory
- `src/geoclaw_qgis/profile/layers.py`
  - 解析 `soul.md`（系统行为边界）与 `user.md`（长期用户偏好）
  - 会话初始化加载，提供 planner/tool-router/report/memory 的统一上下文
  - `apply_dialogue_profile_update()` 支持对话摘要驱动的 profile 覆盖写入（含 soul 安全锁）
- `scripts/geoclaw_case_runner.py`
  - 原生案例统一入口（city/bbox/data-dir）
  - 输出目录强制固定在 `data/outputs`
- `scripts/geoclaw_operator_runner.py`
  - 单算法执行：`--param` / `--param-json` / `--params-file`
  - 执行前做输出安全校验
- `src/geoclaw_qgis/ai/external_client.py`
  - OpenAI/Qwen/Gemini/Ollama provider 统一 client
  - 自动上下文压缩
- `src/geoclaw_qgis/memory/store.py`
  - 短期、长期、归档、向量检索
- `src/geoclaw_qgis/security/output_guard.py`
  - 固定输出根目录 + 禁止 in-place 覆盖输入
- `src/geoclaw_qgis/analysis/network_ops.py`
  - TrackIntel 轨迹处理和 OD 网络分析

## 4. 环境要求

- Python 3.10+
- QGIS 3.32+
- 可调用 `qgis_process`
- GDAL/OGR/PROJ

可选依赖：

```bash
python3 -m pip install --user --break-system-packages 'geoclaw-openai[network]'
```

## 5. 开发安装

```bash
# 1) 环境检查
bash scripts/check_local_env.sh

# 2) 安装 CLI
bash scripts/install_geoclaw_openai.sh

# 3) 初始化
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
geoclaw-openai profile init
geoclaw-openai profile show
geoclaw-openai profile evolve --target user --summary "偏好中文并优先本地模型" --set preferred_language=Chinese --add preferred_tools=Ollama,QGIS
```

## 6. 开发与验证流程

### 6.1 原生案例

```bash
geoclaw-openai run --case native_cases --city "武汉市"
```

### 6.2 单算法（灵活参数）

```bash
geoclaw-openai operator \
  --algorithm native:buffer \
  --params-file configs/examples/operator_buffer_params.yaml
```

### 6.3 自然语言入口

```bash
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute
geoclaw-openai nl "商场选址分析，优先可复现QGIS流程" --use-sre --sre-report-out data/outputs/reasoning/nl_e2e_report.md
```

### 6.4 轨迹网络

```bash
bash scripts/run_trackintel_network_demo.sh
```

### 6.5 day-run

```bash
bash scripts/day_run.sh
```

当前 day-run 覆盖矩阵（v3.2.0）：
- run：`native_cases`、`wuhan_advanced`
- skill：`location_analysis`、`site_selection`（按 API key 自动决定是否附带 AI 总结）
- reasoning：`reasoning --reasoner-mode deterministic --report-out data/outputs/reasoning/day_run_reasoning.md`
- nl：`nl --use-sre --sre-reasoner-mode deterministic --sre-report-out data/outputs/reasoning/day_run_nl_e2e_report.md`
- memory：`memory status/short/long/search`

关键产物校验：
- `data/outputs/wuhan_location/grid_location.gpkg`
- `data/outputs/wuhan_site/site_candidates.gpkg`
- `data/outputs/wuhan_analysis/grid_clustered.gpkg`
- `data/outputs/wuhan_analysis/maps/geoclaw_index.png`
- `data/outputs/reasoning/day_run_reasoning.md`
- `data/outputs/reasoning/day_run_nl_e2e_report.md`

### 6.6 复杂 NL 端到端套件

```bash
bash scripts/e2e_complex_nl_suite.sh
```

覆盖 4 组复杂场景：
- 商场选址 Top-N + SRE 报告
- 本地数据目录区位分析 + SRE 报告
- 轨迹网络分析（显式 out-dir 保留）+ SRE 报告
- Operator 参数列表保留与执行验证

## 7. 配置与环境变量

推荐统一变量：

- `GEOCLAW_AI_PROVIDER`
- `GEOCLAW_AI_BASE_URL`
- `GEOCLAW_AI_API_KEY`
- `GEOCLAW_AI_MODEL`
- `GEOCLAW_AI_TIMEOUT`
- `GEOCLAW_AI_MAX_CONTEXT_CHARS`

兼容变量：`GEOCLAW_OPENAI_*`、`GEOCLAW_QWEN_*`、`GEOCLAW_GEMINI_*`、`GEOCLAW_OLLAMA_*`。
Profile 变量：`GEOCLAW_SOUL_PATH`、`GEOCLAW_USER_PATH`。

## 8. 安全策略

- 输出必须在 `data/outputs` 下。
- 输出不能与输入路径相同。
- 若不满足条件，命令直接失败（`OutputSecurityError`）。

## 9. TODO（开发）

- TODO: 为 `memory search` 增加可选 embedding provider，替换当前哈希向量方案。
- TODO: 为 `nl` 增加多轮上下文追踪与歧义消解。
- TODO: 为 `network` 增加更细粒度质量评估指标（停驻点覆盖率、异常轨迹比例）。
- TODO: 增加 CI 文档一致性检查（CLI 参数与文档示例自动比对）。

## 10. 常见问题

1. `qgis_process not found`
- 在 `onboard` 设置 `--qgis-process`，或导出 `GEOCLAW_OPENAI_QGIS_PROCESS`。

2. `update` 无法检测更新
- 默认跟踪 `origin/main`，如果仓库主分支为 `master`，使用 `--branch master`。

3. AI 认证失败（401/403）
- 检查 provider 与 key 是否匹配，并用 `geoclaw-openai config show` 复核。
