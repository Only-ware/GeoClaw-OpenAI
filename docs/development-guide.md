# GeoClaw-OpenAI 开发指南（v2.1.0）

本文档面向后续开发和维护，说明 GeoClaw 的结构、目的、环境配置、安装运行和扩展方法。  
机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 项目目标

GeoClaw-OpenAI 是一个基于 QGIS Processing (`qgis_process`) 的空间分析与制图框架，核心目标：

- 用 `pipeline.yaml` 管理可复用地理分析流程
- 原生支持区位分析与选址分析
- 支持模板化制图和批量导出
- 支持 Skill 扩展和外部 AI API 接入

## 2. 目录结构与用途

```text
AI-Agents/
├── configs/
│   ├── thematic_maps.yaml              # 专题图模板配置
│   └── skills_registry.json            # Skill 注册表
├── docs/
│   ├── framework-design.md             # 架构设计
│   ├── technical-reference-geoclaw-openai.md # 技术参考（科研/团队）
│   ├── scientist-learning-guide.md      # 科研学习手册（初学者）
│   ├── release-notes.md                 # 版本迭代记录
│   ├── local-env-notes.md              # 本地环境检测结果
│   ├── wuhan-osm-workflow.md           # 武汉综合案例流程
│   ├── native-cases-and-skills.md      # 区位/选址 + Skill 扩展说明
│   └── development-guide.md            # 本文档
├── pipelines/
│   ├── wuhan_geoclaw.yaml              # 武汉综合分析 pipeline
│   └── cases/
│       ├── location_analysis.yaml      # 原生区位分析 pipeline
│       └── site_selection.yaml         # 原生选址分析 pipeline
├── scripts/
│   ├── check_local_env.sh              # 环境检测
│   ├── download_osm_wuhan.py           # OSM 数据下载
│   ├── run_qgis_pipeline.py            # 通用 pipeline 执行器
│   ├── geoclaw_case_runner.py          # 统一案例运行（city/bbox/local-data）
│   ├── geoclaw_operator_runner.py      # 单算法运行（灵活参数）
│   ├── run_location_analysis_case.sh   # 区位分析入口
│   ├── run_site_selection_case.sh      # 选址分析入口
│   ├── run_native_cases.sh             # 一键运行区位+选址
│   ├── geoclaw_skill_runner.py         # Skill 运行器（可调外部 AI）
│   ├── run_wuhan_case.sh               # 武汉综合案例入口
│   ├── day_run.sh                      # 日常回归链路
│   ├── run_beginner_demos.sh           # 栅格/矢量教学 demo
│   └── export_thematic_maps.py         # 批量专题图导出
├── src/geoclaw_qgis/
│   ├── analysis/                       # 区位/选址分析 API 封装
│   ├── providers/                      # qgis_process 执行适配
│   ├── skills/                         # Skill 模型与注册表加载
│   ├── ai/                             # 外部 AI API 客户端
│   ├── core/                           # 基础 pipeline 数据结构
│   └── ...
└── data/
    ├── examples/trajectory/             # 轨迹测试数据与 demo 结果
    ├── raw/                            # 原始数据
    └── outputs/                        # 分析与出图结果
```

## 3. 环境要求

### 3.1 必需依赖

- QGIS 3.32+
- `qgis_process` 命令可调用
- GDAL / OGR / PROJ
- Python 3.10+

### 3.2 推荐配置（本机实测）

- QGIS: `3.32.3-Lima`
- `qgis_process`: `/Applications/QGIS.app/Contents/MacOS/bin/qgis_process`
- GDAL: `3.12.2`
- PROJ: `9.7.1`

### 3.3 注意事项

- 系统 Python 未必可导入 `qgis` 模块，这是正常现象。
- 若需要 PyQGIS，请使用 QGIS 自带 Python。

## 4. 安装与初始化

```bash
# 1) 环境检测
bash scripts/check_local_env.sh

# 2) 安装 geoclaw-openai CLI
bash scripts/install_geoclaw_openai.sh

# 3) 首次配置
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh

# 4) 可选：加入 PATH
export PATH="/Applications/QGIS.app/Contents/MacOS/bin:$PATH"
```

## 5. 运行方式

### 5.1 原生案例

```bash
# 区位分析 + 选址分析
bash scripts/run_native_cases.sh

# 统一 CLI 入口（推荐）
geoclaw-openai run --case native_cases --city "武汉市"
```

产出：

- `data/outputs/wuhan_location/grid_location.gpkg`
- `data/outputs/wuhan_site/site_candidates.gpkg`

### 5.2 武汉综合案例（分析 + 制图）

```bash
bash scripts/run_wuhan_case.sh

# 统一 CLI 入口（高级案例）
geoclaw-openai run --case wuhan_advanced --bbox "30.50,114.20,30.66,114.45" --with-maps
```

### 5.3 输入源模式（city/bbox/local-data）

```bash
# 城市名
geoclaw-openai run --case location_analysis --city "武汉市"

# 边界框
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 本地目录
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download
```

本地目录需要包含：

- `roads.geojson`
- `water.geojson`
- `hospitals.geojson`
- `study_area.geojson`

说明：`--city`、`--bbox`、`--data-dir` 三个输入参数互斥。

### 5.4 单算法灵活参数（operator）

```bash
# 直接传参
geoclaw-openai operator \
  --algorithm native:buffer \
  --param INPUT=data/raw/wuhan_osm/hospitals.geojson \
  --param DISTANCE=1000 \
  --param OUTPUT=data/outputs/demo_operator/hosp_buffer.gpkg

# 通过 YAML/JSON 参数文件
geoclaw-openai operator \
  --algorithm native:buffer \
  --params-file configs/examples/operator_buffer_params.yaml
```

### 5.5 初学者 demo

```bash
bash scripts/run_beginner_demos.sh
```

示例 pipeline：

- `pipelines/examples/vector_basics.yaml`
- `pipelines/examples/raster_basics.yaml`

### 5.6 自然语言入口（nl）

```bash
# 预览自然语言解析结果
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"

# 直接执行解析结果
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute
```

说明：`nl` 当前可解析并转发到 `run`、`operator`、`network`、`skill`、`memory`、`update`。

## 6. 区位分析说明

`pipelines/cases/location_analysis.yaml` 输出以下关键字段：

- `LOCATION_SCORE`
- `LOCATION_LEVEL`
- `ACCESS_NORM`
- `UNDERSERVED_NORM`
- `SAFETY_NORM`

## 7. 选址分析说明

`pipelines/cases/site_selection.yaml` 从区位结果中筛选并排序候选点，输出：

- `SITE_RANK`
- `SITE_SCORE`
- `SITE_CLASS`

## 8. Skill 扩展机制

注册表：`configs/skills_registry.json`

当前支持两类 skill：

- `pipeline`：执行空间分析 pipeline
- `ai`：调用外部 AI API

命令：

```bash
geoclaw-openai skill -- --list
geoclaw-openai skill -- --skill location_analysis
geoclaw-openai skill -- --skill site_selection --with-ai --ai-input "输出建设优先级"
```

## 9. 外部 AI API 配置

采用 OpenAI-compatible `/chat/completions` 协议。

环境变量：

- `GEOCLAW_OPENAI_BASE_URL`
- `GEOCLAW_OPENAI_API_KEY`
- `GEOCLAW_OPENAI_MODEL`

## 10. 轨迹与复杂网络模块（Trackintel）

轨迹数据测试样例位于：`data/examples/trajectory/trackintel_demo_pfs.csv`。  
demo 结果输出位于：`data/examples/trajectory/results/network_trackintel_demo/`。

运行命令：

```bash
bash scripts/run_trackintel_network_demo.sh
```

算法来源说明：轨迹处理主链路基于 [Track-Intel（MIE Lab）](https://github.com/mie-lab/trackintel)。
- `GEOCLAW_OPENAI_TIMEOUT`（可选）

## 10. 扩展开发建议

- 增加 pipeline schema 校验（类型、必填项、参数合法性）
- 将选址可达性从欧式距离升级为路网最短路径
- 将静态分级断点升级为分位数/Jenks 自动分级
- 为 Skill 增加插件命令钩子和权限边界



## 11. CLI Onboard 参数

`geoclaw-openai onboard` 支持设置以下参数：

- `--api-key`
- `--ai-base-url`
- `--ai-model`
- `--qgis-process`
- `--default-bbox`
- `--registry`
- `--workspace`
- `--non-interactive`

示例：

```bash
geoclaw-openai onboard --non-interactive \
  --api-key "<OPENAI_KEY>" \
  --ai-base-url "https://api.openai.com/v1" \
  --ai-model "gpt-4.1-mini" \
  --default-bbox "30.50,114.20,30.66,114.45"
```
