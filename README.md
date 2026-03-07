# GeoClaw-OpenAI (v2.1.0)

GeoClaw-OpenAI 是一个基于 `QGIS Processing (qgis_process)` 的空间分析与制图框架，面向科研与工程团队，支持从数据获取、分析建模、制图导出到 AI 辅助解释的完整闭环。

机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 核心能力总览

- 空间分析：内置区位分析、选址分析、武汉综合案例（含聚类）。
- 制图导出：批量专题图导出（PNG）+ QGIS 工程文件（QGZ）。
- 自然语言操作（重点）：`geoclaw-openai nl "..."` 可将中文任务转换为可执行命令。
- Skill 扩展（重点）：注册式技能编排，支持 `pipeline` 与 `ai` 两类 skill。
- 任务记忆 Memory（重点）：每次任务自动记录短期 memory，自动复盘归档长期 memory。
- 复杂网络分析（新增）：融合 `trackintel` 生成 OD 网络、中心性与社群指标。
- 自更新：`geoclaw-openai update` 检查并拉取最新版本。
- 灵活参数：`run`/`operator` 支持城市名、bbox、本地目录、JSON/YAML 参数覆盖。

## 2. 为什么是 v2.1

v2.1.0 聚焦“轨迹数据处理 + 复杂网络分析”的工程化落地：

- 引入轨迹测试数据目录：`data/examples/trajectory/`。
- 融合 `trackintel` 的轨迹预处理与 OD 网络构建流程。
- 提供可复现 demo：`scripts/run_trackintel_network_demo.sh`。
- 产出示例结果：`data/examples/trajectory/results/network_trackintel_demo/`。

## 3. 安装与初始化

```bash
# 1) 环境检测
bash scripts/check_local_env.sh

# 2) 安装 CLI
bash scripts/install_geoclaw_openai.sh

# 3) 首次配置（API Key / qgis_process / 默认参数）
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
```

说明：

- `source ~/.geoclaw-openai/env.sh` 会自动补齐 Python user bin 到 `PATH`。
- 配置文件位于 `~/.geoclaw-openai/`（`config.json` / `.env` / `env.sh`）。

## 4. 自然语言操作（NL）

### 4.1 预览模式（默认）

```bash
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"
```

会返回：

- `intent`：识别到的任务类型（如 `run`）。
- `command_preview`：解析后的 CLI 命令。
- `cli_args`：结构化参数，可审计、可复用。

### 4.2 执行模式

```bash
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute
```

当前 NL 支持解析并转发到：

- `run`
- `operator`
- `network`
- `skill`
- `memory`
- `update`

## 5. Skill 能力

Skill 由 `configs/skills_registry.json` 管理，支持依赖链（`pre_steps`）与 AI 总结。

```bash
# 查看技能列表
geoclaw-openai skill -- --list

# 运行区位分析 skill
geoclaw-openai skill -- --skill location_analysis

# 运行选址 skill，并调用外部 AI 总结
geoclaw-openai skill -- --skill site_selection --with-ai --ai-input "输出实施优先级"
```

外部 AI API 相关环境变量：

- `GEOCLAW_OPENAI_BASE_URL`
- `GEOCLAW_OPENAI_API_KEY`
- `GEOCLAW_OPENAI_MODEL`

## 6. Memory 能力

每次 CLI 任务（除 `memory` 命令自身）自动执行：

1. 写入短期 memory（任务参数、状态、返回码、错误）。
2. 自动复盘并写入长期 memory（summary / lessons / next_actions）。

存储路径：

- 短期：`~/.geoclaw-openai/memory/short/*.json`
- 长期：`~/.geoclaw-openai/memory/long_term.jsonl`

常用命令：

```bash
# 查看 memory 状态
geoclaw-openai memory status

# 查看最近短期任务
geoclaw-openai memory short --limit 10

# 查看长期复盘记录
geoclaw-openai memory long --limit 10

# 手工复盘指定任务（写入长期 memory）
geoclaw-openai memory review --task-id "<TASK_ID>" --summary "本次实验结论"
```

## 7. 标准分析入口（run）

支持三种输入源（互斥）：

- `--city`：城市名（自动地理编码与数据下载）
- `--bbox`：经纬度边界（`south,west,north,east`）
- `--data-dir`：本地数据目录（跳过下载）

```bash
# 城市名：区位+选址一体化
geoclaw-openai run --case native_cases --city "武汉市"

# bbox：区位分析
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 本地目录：选址分析
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download

# 高级案例 + 出图
geoclaw-openai run --case wuhan_advanced --city "武汉市" --with-maps
```

本地目录最少需要：

- `roads.geojson`
- `water.geojson`
- `hospitals.geojson`
- `study_area.geojson`

## 8. 单算法入口（operator）

适合快速试验某个 QGIS 算法。

```bash
# 参数文件方式
geoclaw-openai operator --algorithm native:buffer --params-file configs/examples/operator_buffer_params.yaml

# 命令行参数方式
geoclaw-openai operator \
  --algorithm native:buffer \
  --param INPUT=data/raw/wuhan_osm/hospitals.geojson \
  --param-json DISTANCE=1000 \
  --param OUTPUT=data/outputs/demo_operator/hosp_buffer_1000m.gpkg
```

## 9. 复杂网络分析（trackintel）

用于轨迹数据的复杂网络分析（OD 网络、中心性、社群）：

算法来源：本模块轨迹处理主链路来自 [Track-Intel（MIE Lab）](https://github.com/mie-lab/trackintel) 的 staypoint/location/trip 处理方法，并在 GeoClaw 中封装为 `geoclaw-openai network`。

```bash
# 安装可选依赖（推荐）
python3 -m pip install --user --break-system-packages 'geoclaw-openai[network]'

# 基于位置点轨迹 CSV 构建复杂网络
geoclaw-openai network \
  --pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv \
  --out-dir data/examples/trajectory/results/network_trackintel_demo \
  --activity-time-threshold 5 \
  --location-epsilon 80 \
  --location-min-samples 1 \
  --location-agg-level dataset
```

主要输出：

- `od_edges.csv`：OD 边权重（流量、用户数、时长统计）
- `od_nodes.csv`：节点复杂网络指标（度、强度、中心性、社群）
- `od_trips.csv`：轨迹级 OD 明细（含起讫 location 映射）
- `network_summary.json`：运行参数与统计摘要

基于仓库内测试数据（`data/examples/trajectory/trackintel_demo_pfs.csv`）的示例结果：

- `positionfixes=40`
- `staypoints=4`
- `locations=4`
- `trips_with_locations=2`
- `od_edges=2`
- `od_nodes=3`

## 10. 自更新能力（update）

```bash
# 仅检查更新
geoclaw-openai update --check-only

# 拉取并更新（默认 origin/main）
geoclaw-openai update
```

说明：网络不可达时会返回 warning 并降级，不会直接导致流程崩溃。

## 11. 一键 Demo 清单（建议按顺序）

### Demo A：自然语言到执行

```bash
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"
geoclaw-openai nl "用武汉市做选址分析，前20个，出图" --execute
```

### Demo B：Skill + AI

```bash
geoclaw-openai skill -- --skill site_selection --with-ai --ai-input "给出三阶段建设建议"
```

### Demo C：Memory 复盘

```bash
geoclaw-openai memory short --limit 5
geoclaw-openai memory long --limit 5
```

### Demo D：教学样例

```bash
bash scripts/run_beginner_demos.sh
```

### Demo E：日常回归

```bash
bash scripts/day_run.sh
```

说明：若未配置真实 `GEOCLAW_OPENAI_API_KEY`，day-run 会默认跳过 AI 总结步骤。可用 `GEOCLAW_OPENAI_DAY_RUN_WITH_AI=1` 强制启用。

### Demo F：复杂网络分析（trackintel）

```bash
bash scripts/run_trackintel_network_demo.sh
```

## 12. 输出结果与目录

常见输出目录：

- `data/outputs/<tag>_location/`：区位分析结果
- `data/outputs/<tag>_site/`：选址分析结果
- `data/outputs/<tag>_analysis/`：综合分析与地图产物

常见关键结果：

- `grid_location.gpkg`
- `site_candidates.gpkg`
- `grid_clustered.gpkg`
- `data/examples/trajectory/results/network_trackintel_demo/od_edges.csv`
- `data/examples/trajectory/results/network_trackintel_demo/od_nodes.csv`
- `data/examples/trajectory/results/network_trackintel_demo/od_trips.csv`
- `maps/*.png`
- `pipeline_report.json`

## 13. 命令速查

```bash
geoclaw-openai --help
geoclaw-openai run --help
geoclaw-openai operator --help
geoclaw-openai network --help
geoclaw-openai skill -- --help
geoclaw-openai memory --help
geoclaw-openai update --help
geoclaw-openai nl --help
```

## 14. 关键工程入口

- 区位案例：`pipelines/cases/location_analysis.yaml`
- 选址案例：`pipelines/cases/site_selection.yaml`
- 武汉综合案例：`pipelines/wuhan_geoclaw.yaml`
- 通用 pipeline 执行器：`scripts/run_qgis_pipeline.py`
- 单算法执行器：`scripts/geoclaw_operator_runner.py`
- 复杂网络执行器（trackintel）：`geoclaw-openai network`
- 复杂网络 demo 脚本：`scripts/run_trackintel_network_demo.sh`
- 案例执行器：`scripts/geoclaw_case_runner.py`
- Skill 运行器：`scripts/geoclaw_skill_runner.py`
- Skill 注册表：`configs/skills_registry.json`
- 日常回归脚本：`scripts/day_run.sh`

## 15. 文档导航

- 技术参考：`docs/technical-reference-geoclaw-openai.md`
- 开发指南：`docs/development-guide.md`
- 科研学习手册：`docs/scientist-learning-guide.md`
- 原生案例与 Skill：`docs/native-cases-and-skills.md`
- CLI 安装与初始化：`docs/cli-onboard.md`
- 版本记录：`docs/release-notes.md`
- Changelog：`CHANGELOG.md`
- 武汉流程：`docs/wuhan-osm-workflow.md`
- 本地环境说明：`docs/local-env-notes.md`

## 16. License

详见 `LICENSE`。
