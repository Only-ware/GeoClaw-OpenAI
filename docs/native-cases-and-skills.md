# GeoClaw 原生案例与 Skill 扩展（v1.1.0）

机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 0. CLI 安装与初始化

```bash
bash scripts/install_geoclaw_openai.sh
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
```

## 1. 原生案例

GeoClaw 现内置两个典型 GIS 功能案例：

- 区位分析（`location_analysis`）
- 选址分析（`site_selection`）

### 1.1 区位分析

配置：`pipelines/cases/location_analysis.yaml`

输出：`data/outputs/wuhan_location/grid_location.gpkg`

核心字段：

- `LOCATION_SCORE`：区位综合评分
- `LOCATION_LEVEL`：A/B/C/D 区位等级
- `UNDERSERVED_NORM`：服务不足强度
- `ACCESS_NORM`：可达性归一化

运行：

```bash
bash scripts/run_location_analysis_case.sh

# 或使用统一 CLI（支持城市名/bbox/本地目录）
geoclaw-openai run --case location_analysis --city "武汉市"
```

### 1.2 选址分析

配置：`pipelines/cases/site_selection.yaml`

输出：`data/outputs/wuhan_site/site_candidates.gpkg`

核心字段：

- `SITE_RANK`：候选点排名
- `SITE_SCORE`：选址综合评分
- `SITE_CLASS`：候选等级（A/B/C）

运行：

```bash
bash scripts/run_site_selection_case.sh

# 或使用统一 CLI
geoclaw-openai run --case site_selection --bbox "30.50,114.20,30.66,114.45"
```

一键运行两个案例：

```bash
bash scripts/run_native_cases.sh

# 或使用统一 CLI
geoclaw-openai run --case native_cases --city "武汉市"
```

### 1.3 三种输入源说明（新增）

- `--city`：按城市名地理编码并下载 OSM 数据。
- `--bbox`：按边界框下载 OSM 数据。
- `--data-dir`：直接使用本地数据目录（目录需含 `roads.geojson`、`water.geojson`、`hospitals.geojson`、`study_area.geojson`）。
- 三者互斥，一次运行只能指定一种输入方式。

示例：

```bash
# 城市名
geoclaw-openai run --case native_cases --city "武汉市"

# bbox
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 本地目录
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download
```

## 2. Skill 扩展机制

GeoClaw 支持通过注册表扩展技能。

注册表：`configs/skills_registry.json`

当前内置 skill：

- `location_analysis`（pipeline）
- `site_selection`（pipeline）
- `ai_planning_assistant`（ai）

### 2.1 查看和运行技能

```bash
# 列出技能
geoclaw-openai skill -- --list

# 运行区位分析技能
geoclaw-openai skill -- --skill location_analysis

# 运行选址分析技能（会先确保区位分析产物）
geoclaw-openai skill -- --skill site_selection
```

## 3. 外部 AI API 输入支持

GeoClaw 使用 OpenAI-compatible Chat Completions 接口。

环境变量：

- `GEOCLAW_OPENAI_BASE_URL`
- `GEOCLAW_OPENAI_API_KEY`
- `GEOCLAW_OPENAI_MODEL`
- `GEOCLAW_OPENAI_TIMEOUT`（可选，默认 60）

### 3.1 对 pipeline 结果做 AI 总结

```bash
geoclaw-openai skill -- --skill site_selection --with-ai --ai-input "请重点关注候选点的公平性和可实施性"
```

### 3.2 独立调用 AI Skill

```bash
geoclaw-openai skill -- --skill ai_planning_assistant --ai-input "根据武汉结果给出三阶段建设策略"
```

## 4. 新增 Skill 的最小步骤

1. 在 `configs/skills_registry.json` 增加 skill 项。
2. 对 `pipeline` 类型：填写 `pipeline` 路径、`report_path`。
3. 对 `ai` 类型：填写 `system_prompt`。
4. 用 `geoclaw-openai skill -- --list` 检查加载。
