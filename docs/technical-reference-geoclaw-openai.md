# GeoClaw-OpenAI 技术参考（科研与团队版，v1.1.0）

更新时间：2026-03-07（Asia/Shanghai）  
机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 项目定位

`geoclaw-openai` 是一个基于 QGIS Processing（`qgis_process`）的空间分析与制图框架，目标是为科研与工程团队提供：

- 可复现的空间分析流水线（YAML pipeline）
- 原生区位分析与选址分析能力
- 标准化专题图导出能力
- 可扩展的 Skill 机制与外部 AI API 接入能力

核心思想：将“数据下载 -> 空间分析 -> 结果制图 -> AI 解释”串联为可自动化、可审计、可扩展的工程流程。

## 2. 工程结构与职责

```text
AI-Agents/
├── configs/
│   ├── skills_registry.json                # Skill 注册中心
│   ├── thematic_maps.yaml                  # 专题图模板
│   └── examples/                           # 参数覆盖与 operator 示例参数
├── data/
│   ├── raw/wuhan_osm/                      # OSM 原始数据
│   └── outputs/                            # 分析结果与地图输出
├── docs/
│   ├── technical-reference-geoclaw-openai.md
│   ├── development-guide.md
│   ├── native-cases-and-skills.md
│   └── ...
├── pipelines/
│   ├── wuhan_geoclaw.yaml                  # 综合分析案例
│   ├── cases/
│       ├── location_analysis.yaml          # 区位分析
│       └── site_selection.yaml             # 选址分析
│   └── examples/                           # 栅格/矢量教学 pipeline
├── scripts/
│   ├── day_run.sh                          # 一键日常回归
│   ├── download_osm_wuhan.py               # OSM 下载与转 GeoJSON
│   ├── geoclaw_case_runner.py              # 统一案例运行（city/bbox/local-data）
│   ├── geoclaw_operator_runner.py          # 单算法灵活运行（param/json/file）
│   ├── run_qgis_pipeline.py                # 通用 pipeline 执行器
│   ├── geoclaw_skill_runner.py             # Skill 编排执行
│   ├── export_thematic_maps.py             # 批量专题图导出
│   ├── install_geoclaw_openai.sh           # CLI 安装
│   ├── run_beginner_demos.sh               # 栅格/矢量教学 demo
│   └── run_*_case.sh                       # 各案例入口脚本
├── src/geoclaw_qgis/
│   ├── cli/main.py                         # geoclaw-openai CLI
│   ├── config.py                           # 运行时配置与环境变量
│   ├── memory/store.py                     # 短期/长期 memory 存储与复盘
│   ├── core/                               # Pipeline/Step 数据结构
│   ├── providers/                          # qgis_process provider
│   ├── skills/                             # Skill 模型与注册
│   ├── ai/external_client.py               # OpenAI-compatible 客户端
│   └── analysis/                           # Python API 封装入口
└── pyproject.toml
```

运行期 memory 不在仓库内，默认位于 `~/.geoclaw-openai/memory/`。

## 3. 实现原理（端到端）

## 3.1 数据层

`scripts/download_osm_wuhan.py` 使用 Overpass API 抓取 bbox 数据，并拆分为：

- `roads.geojson`
- `water.geojson`
- `hospitals.geojson`
- `study_area.geojson`

该脚本支持两种输入：

- `--city`（通过 Nominatim 地理编码得到 bbox）
- `--bbox`（直接指定边界）

并具备多端点重试；案例脚本支持“下载失败后使用本地缓存继续执行”。

`scripts/geoclaw_case_runner.py` 进一步统一了三种输入模式：

- 城市名 `--city`
- 边界框 `--bbox`
- 本地数据目录 `--data-dir`

以上三种输入参数互斥，一次运行仅选择一种。

`scripts/geoclaw_operator_runner.py` 支持单算法灵活运行，参数来源可组合：

- `--param KEY=VALUE`
- `--param-json KEY=JSON`
- `--params-file file.(json|yaml)`

## 3.2 流水线执行层

`scripts/run_qgis_pipeline.py` 执行 YAML 中的 `steps`：

1. 解析 `variables` 和 `${var}` 模板
2. 按顺序组装 `qgis_process --json run ...`
3. 逐步记录输入/输出，写入 `pipeline_report.json`
4. 通过 `step_id.OUTPUT` 将上游输出注入下游参数

为支持日常重跑，执行器会在每一步开始前清理已有输出文件，避免 GPKG/TIF 覆写失败。
同时支持 `--set` / `--set-json` / `--vars-file` 三种变量覆盖方式，便于实验参数迭代。

## 3.3 空间分析层

### 区位分析（`pipelines/cases/location_analysis.yaml`）

主要过程：

- 统一投影到 `EPSG:32650`
- 2km 网格化
- 路网长度统计（`sumlinelengths`）
- 医疗服务覆盖叠加（`buffer` + `calculatevectoroverlaps`）
- 医疗热点核密度（`heatmapkerneldensityestimation`）
- 最近医疗点距离（`distancetonearesthubpoints`）
- 多指标标准化与综合评分（`fieldcalculator`）

核心产物：`grid_location.gpkg`，关键字段包括：

- `LOCATION_SCORE`
- `LOCATION_LEVEL`
- `ACCESS_NORM`
- `UNDERSERVED_NORM`
- `SAFETY_NORM`

### 选址分析（`pipelines/cases/site_selection.yaml`）

主要过程：

- 可行区域过滤（安全性、服务缺口等约束）
- `SITE_SCORE` 计算
- 自动排序生成 `SITE_RANK`
- 分级生成 `SITE_CLASS`
- 提取 Top-N 候选并转中心点

核心产物：`site_candidates.gpkg`。

## 3.4 制图层

`scripts/export_thematic_maps.py` 读取 `configs/thematic_maps.yaml` 批量渲染专题图（PNG）并输出 QGIS 工程文件：

- `geoclaw_index.png`
- `road_intensity.png`
- `accessibility.png`
- `hotspot.png`
- `thematic_maps.qgz`

脚本已对 QGIS/GDAL 的 PNG 已知噪声告警进行了过滤，避免影响自动化日志判读。

## 3.5 Skill 与 AI 扩展层

`scripts/geoclaw_skill_runner.py` 通过 `configs/skills_registry.json` 装配能力：

- `pipeline` skill：执行一个 pipeline
- `pre_steps`：支持依赖链（如 `site_selection` 依赖 `location_analysis`）
- `ai` skill：调用 `ExternalAIClient` 走 OpenAI-compatible `/chat/completions`

该机制使 GeoClaw 支持“空间分析 + AI 总结”的可维护扩展。

## 3.6 Memory 与自更新层

`geoclaw-openai` 在 CLI 主入口内置任务记忆机制：

- 每次任务（除 `memory` 命令自身）先写入短期 memory。
- 任务结束后自动生成复盘总结，并写入长期 memory。

数据位置：

- 短期：`~/.geoclaw-openai/memory/short/<task_id>.json`
- 长期：`~/.geoclaw-openai/memory/long_term.jsonl`

同时新增自更新能力：

- `geoclaw-openai update --check-only`：检查 `origin/main` 是否有更新。
- `geoclaw-openai update`：拉取最新代码并执行 editable 安装刷新本地 CLI。

## 4. 配置与环境变量

通过 `geoclaw-openai onboard` 写入 `~/.geoclaw-openai/`：

- `config.json`
- `.env`
- `env.sh`

关键环境变量：

- `GEOCLAW_OPENAI_HOME`
- `GEOCLAW_OPENAI_QGIS_PROCESS`
- `GEOCLAW_OPENAI_BASE_URL`
- `GEOCLAW_OPENAI_API_KEY`
- `GEOCLAW_OPENAI_MODEL`
- `GEOCLAW_OPENAI_TIMEOUT`
- `GEOCLAW_OPENAI_SKILL_REGISTRY`
- `GEOCLAW_OPENAI_DEFAULT_BBOX`

## 5. 安装与运行

## 5.1 依赖要求

- QGIS 3.32+
- 可调用 `qgis_process`
- Python 3.10+
- GDAL/OGR/PROJ

## 5.2 安装与初始化

```bash
bash scripts/check_local_env.sh
bash scripts/install_geoclaw_openai.sh
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
```

## 5.3 运行示例

```bash
# 原生区位+选址
bash scripts/run_native_cases.sh

# 武汉综合分析+出图
bash scripts/run_wuhan_case.sh

# 城市名驱动（推荐）
geoclaw-openai run --case native_cases --city "武汉市"

# bbox 驱动
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 本地目录驱动
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download

# Skill 链路
geoclaw-openai skill -- --list
geoclaw-openai skill -- --skill site_selection --with-ai --ai-input "输出实施优先级"

# Memory 查看
geoclaw-openai memory status
geoclaw-openai memory short --limit 5
geoclaw-openai memory long --limit 5

# 自更新
geoclaw-openai update --check-only
```

## 5.4 日常回归（day-run）

```bash
bash scripts/day_run.sh
```

包含：安装 -> onboard -> 原生案例 -> 武汉综合案例 -> skill 链路 -> 产物校验。

## 6. 已完成的 day-run 验证（2026-03-07）

执行命令：`bash scripts/day_run.sh`

结果：

- 安装与 CLI 初始化通过
- 原生区位/选址 pipeline 可重复执行通过
- 武汉综合分析与专题图导出通过
- skill 依赖链执行通过
- 产物校验通过

说明：

- 若未提供真实 `GEOCLAW_OPENAI_API_KEY`，day-run 默认跳过 AI 摘要步骤，只验证空间流程主链路。
- 可通过 `GEOCLAW_OPENAI_DAY_RUN_WITH_AI=1` 强制启用 AI 摘要步骤（需可用 API key）。

## 7. 可复现性与科研使用建议

- 固定 `bbox`、投影、网格尺寸、评分权重后可复现实验输出。
- 保留每次运行的 `pipeline_report.json` 作为审计记录。
- 对不同城市建议复制案例 YAML 并建立 `city_xxx/` 输出目录，避免结果覆盖。
- 论文/报告建议同步记录 OSM 抓取时间与 Overpass endpoint。

## 8. 扩展开发路径

1. 新增空间案例：复制一个 pipeline 文件并注册到 skill registry。
2. 新增评分逻辑：在 `fieldcalculator` 中增字段并调整综合公式。
3. 新增 AI 能力：在 `skills_registry.json` 增加 `ai` 类型 skill 与 system prompt。
4. 新增 skill 类型：扩展 `geoclaw_skill_runner.py`（当前含 TODO：command/plugin 类型）。

## 9. 主要 TODO（代码内已标注）

- pipeline 配置 schema 校验与类型约束（`run_qgis_pipeline.py`）
- 距离算法从欧氏距离升级到路网最短路径（案例 YAML）
- 动态分级与更丰富制图模板（`thematic_maps.yaml`/制图脚本）
- skill 插件命令类型与沙箱执行边界（`geoclaw_skill_runner.py`）
- 缓存数据新鲜度与 bbox 一致性校验（案例脚本）

## 10. 风险与边界

- OSM 数据完整性受采集时点影响。
- Overpass 服务可用性会波动，当前采用重试+缓存回退策略。
- 当前选址模型为启发式加权模型，不等价于严格最优化选址（可后续引入 MCLP/最大覆盖等模型）。
