# GeoClaw-OpenAI (v1.0.0)

基于 `qgis_process` 的 GeoClaw 风格地理处理与制图框架。

机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 当前能力

- `pipeline.yaml` 驱动的可配置空间分析流程
- 原生区位分析与选址分析案例
- 专题图模板与批量导出
- Skill 扩展机制（注册表 + 外部 AI API 输入）
- 本地环境检测（QGIS CLI / PyQGIS / GDAL）
- 栅格/矢量教学 demo 与单算法灵活运行（`operator`）

## 快速开始

```bash
# 1) 环境检测
bash scripts/check_local_env.sh

# 2) 安装 geoclaw-openai CLI
bash scripts/install_geoclaw_openai.sh

# 3) 首次配置（OpenAI API Key、qgis_process、默认参数）
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh

# 4) 跑原生案例（区位 + 选址）
bash scripts/run_native_cases.sh

# 5) 批量专题图（武汉综合案例）
bash scripts/run_wuhan_case.sh

# 6) 日常回归（安装+案例+skill+产物校验）
bash scripts/day_run.sh

# 7) 初学者栅格/矢量 demo
bash scripts/run_beginner_demos.sh
```

## Skill 扩展

```bash
# 列出 skills
geoclaw-openai skill -- --list

# 运行选址 skill，并用外部 AI 做总结
geoclaw-openai skill -- --skill site_selection --with-ai --ai-input "输出实施优先级"
```

外部 AI API 需设置：

- `GEOCLAW_OPENAI_BASE_URL`
- `GEOCLAW_OPENAI_API_KEY`
- `GEOCLAW_OPENAI_MODEL`

## 关键入口

- 区位案例：`pipelines/cases/location_analysis.yaml`
- 选址案例：`pipelines/cases/site_selection.yaml`
- 通用 pipeline 执行器：`scripts/run_qgis_pipeline.py`
- Skill 运行器：`scripts/geoclaw_skill_runner.py`
- Skill 注册表：`configs/skills_registry.json`
- 武汉高级案例：`pipelines/wuhan_geoclaw.yaml`
- 通用案例运行器：`scripts/geoclaw_case_runner.py`
- 单算法运行器：`scripts/geoclaw_operator_runner.py`
- 教学 demo 脚本：`scripts/run_beginner_demos.sh`

## 按输入源运行分析（新增）

支持三种输入方式：

- 城市名（自动地理编码 -> bbox -> OSM 下载）
- 经度纬度边界（bbox）
- 本地数据目录（跳过下载）

统一命令：

```bash
# 1) 用城市名运行区位+选址
geoclaw-openai run --case native_cases --city "武汉市"

# 2) 用 bbox 运行区位分析
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 3) 用本地数据目录运行（目录内需 4 个文件）
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download

# 4) 单算法灵活运行（参数文件/JSON）
geoclaw-openai operator --algorithm native:buffer --params-file configs/examples/operator_buffer_params.yaml
```

注意：`--city`、`--bbox`、`--data-dir` 三个参数互斥，一次只能使用一种输入源。

本地数据目录最少包含：

- `roads.geojson`
- `water.geojson`
- `hospitals.geojson`
- `study_area.geojson`

## 文档

- 技术参考（科研与团队）：`docs/technical-reference-geoclaw-openai.md`
- 科研学习手册（初学者）：`docs/scientist-learning-guide.md`
- 版本迭代记录：`docs/release-notes.md`
- v1.0 正式说明书（DOCX）：`GeoClaw-OpenAI_v1.0_工程说明书.docx`
- 架构设计：`docs/framework-design.md`
- 开发指南：`docs/development-guide.md`
- CLI 安装与初始化：`docs/cli-onboard.md`
- 原生案例与 Skill：`docs/native-cases-and-skills.md`
- 武汉流程：`docs/wuhan-osm-workflow.md`
- 本地环境说明：`docs/local-env-notes.md`
