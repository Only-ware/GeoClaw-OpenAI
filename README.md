# GeoClaw-OpenAI (v2.4.0)

GeoClaw-OpenAI 是一个基于 `QGIS Processing (qgis_process)` 的空间分析与制图工具链，面向科研和工程团队，支持从数据获取、分析建模、结果制图到 AI 解释的完整流程。

机构：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. v2.4.0 新增能力（重点）

本次版本重点新增以下能力：

1. Soul/User 双层个性化架构（新增）
- `soul.md`：系统身份、地理推理原则、执行边界（系统级高优先级）。
- `user.md`：用户长期画像与偏好（个性化软约束，不覆盖安全边界）。
- 会话初始化自动加载并解析为结构化对象，供 planner/tool-router/report/memory 使用。

2. 新增 profile CLI（新增）
- `geoclaw-openai profile init`：初始化 `~/.geoclaw-openai/soul.md` 与 `user.md`。
- `geoclaw-openai profile show`：查看当前加载路径与结构化摘要。

3. 商场选址 Skill 双写法（延续）
- `mall_site_selection_llm`：大模型策略推理写法。
- `mall_site_selection_qgis`：QGIS Processing 可复现计算写法。

4. Skill 注册前安全门禁（延续）
- 新增 `skill-registry assess` 与 `skill-registry register`。
- 注册前自动评估风险等级；`high` 风险默认阻断。
- 注册动作必须用户确认（`--confirm` 或交互 `YES`）。

5. Skill 编写规范文档（延续）
- 新增 Skill 编写规范与评审清单。
- 新增安全门禁说明与高危样例。

6. 模型与运行链路同步
- 默认模型保持最新族：`gpt-5-mini`、`qwen-plus-latest`、`gemini-flash-latest`。
- `day_run`、CLI 默认配置与文档示例一致。

### 1.1 新增能力简要使用

```bash
# 初始化/查看 profile layers
geoclaw-openai profile init
geoclaw-openai profile show

# 商场选址：LLM 写法
geoclaw-openai skill -- --skill mall_site_selection_llm --ai-input "给出武汉商场选址策略"

# 商场选址：QGIS 写法
geoclaw-openai skill -- --skill mall_site_selection_qgis --skip-download

# 注册前安全评估
geoclaw-openai skill-registry assess --spec-file configs/examples/high_risk_skill_injection.json

# 注册（需要确认）
geoclaw-openai skill-registry register --spec-file configs/examples/new_skill.json --confirm
```

## 2. 核心能力总览

- 区位分析、选址分析、武汉综合案例（含聚类）
- 批量专题图导出（PNG）+ QGIS 工程文件（QGZ）
- 自然语言操作（`geoclaw-openai nl`）
- Skill 扩展（`pipeline` / `ai`）
- Memory 任务闭环（短期 + 长期复盘）
- Mobility（轨迹）分析（Track-Intel 融合）
- 自更新能力（`geoclaw-openai update`）

## 3. 安装与初始化

```bash
# 1) 环境检测
bash scripts/check_local_env.sh

# 2) 安装 CLI
bash scripts/install_geoclaw_openai.sh

# 3) 首次配置（交互式）
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
```

非交互配置示例：

```bash
# OpenAI
geoclaw-openai onboard --non-interactive \
  --ai-provider openai \
  --api-key "<OPENAI_KEY>" \
  --ai-model "gpt-5-mini"

# Qwen
geoclaw-openai onboard --non-interactive \
  --ai-provider qwen \
  --api-key "<QWEN_KEY>" \
  --ai-model "qwen-plus-latest"

# Gemini
geoclaw-openai onboard --non-interactive \
  --ai-provider gemini \
  --api-key "<GEMINI_KEY>" \
  --ai-model "gemini-flash-latest"
```

## 4. 后期切换模型/Provider（无需重装）

```bash
# 查看当前配置
geoclaw-openai config show

# 切换 provider + 模型
geoclaw-openai config set --ai-provider openai --ai-model gpt-5.4
geoclaw-openai config set --ai-provider qwen --ai-model qwen3-max
geoclaw-openai config set --ai-provider gemini --ai-model gemini-3.1-pro-preview

# 可同时改 base_url / key
geoclaw-openai config set --ai-provider gemini --ai-base-url "https://generativelanguage.googleapis.com/v1beta/openai" --api-key "<GEMINI_KEY>"
```

> GeoClaw-OpenAI 不限制具体模型名：`--ai-model` 可填写任意 provider 当前可用的模型 ID。

## 4.1 可用模型名称（2026-03-07 已核验）

以下模型名来自各官方文档，可直接用于 `--ai-model`：

- OpenAI（官方 models 页）  
  来源：[OpenAI Models](https://platform.openai.com/docs/models)
  - `gpt-5.4`
  - `gpt-5.4-pro`
  - `gpt-5-mini`
  - `gpt-5-nano`

- Gemini（Google AI for Developers）  
  来源：[Gemini Models](https://ai.google.dev/gemini-api/docs/models)
  - `gemini-3.1-pro-preview`
  - `gemini-3.1-flash-lite-preview`
  - `gemini-3-flash-preview`
  - `gemini-flash-latest`（别名）

- Qwen（阿里云 Model Studio）  
  来源：[Qwen 模型列表](https://help.aliyun.com/zh/model-studio/models)
  - `qwen3-max`
  - `qwen3.5-plus`
  - `qwen3.5-flash`
  - `qwen-max-latest` / `qwen-plus-latest` / `qwen-turbo-latest` / `qwen-long-latest`（别名）

建议：
- 先用 `*-latest` 别名减少文档老化。
- 追求可复现时，改用固定版本模型名。

## 5. 自然语言入口

```bash
# 默认预览
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"

# 直接执行
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute
```

当前 NL 覆盖：`run` / `operator` / `network` / `skill` / `memory` / `update`。
在 v2.4.0 中，NL 规划会读取 `soul.md/user.md`，并在商场选址等场景触发注册 Skill 优先路由。

## 6. Memory：记录、复盘、归档、检索

```bash
# 状态 / 列表
geoclaw-openai memory status
geoclaw-openai memory short --limit 10
geoclaw-openai memory long --limit 10

# 手工复盘入长期记忆
geoclaw-openai memory review --task-id "<TASK_ID>" --summary "本次实验结论"

# 归档旧短期记忆（默认 7 天前）
geoclaw-openai memory archive --before-days 7

# 向量检索历史记忆
geoclaw-openai memory search --query "network 输出安全" --scope all --top-k 5
```

Memory 路径：
- 短期：`~/.geoclaw-openai/memory/short/`
- 长期：`~/.geoclaw-openai/memory/long_term.jsonl`
- 归档：`~/.geoclaw-openai/memory/archive/short/`

## 7. 安全机制（固定输出目录）

安全策略：
- 输出必须落在 `data/outputs` 下。
- 禁止输出路径与输入路径相同（防止覆盖或删除输入数据）。

示例：

```bash
# 合法（输出在 data/outputs 下）
geoclaw-openai operator \
  --algorithm native:buffer \
  --param INPUT=data/raw/wuhan_osm/hospitals.geojson \
  --param OUTPUT=data/outputs/demo_operator/hosp_buffer.gpkg \
  --dry-run

# 非法（会被拦截）
geoclaw-openai operator \
  --algorithm native:buffer \
  --param INPUT=data/raw/wuhan_osm/hospitals.geojson \
  --param OUTPUT=data/raw/wuhan_osm/hospitals.geojson \
  --dry-run
```

## 8. 标准分析入口（run）

`geoclaw-openai run` 支持 3 种输入源（互斥）：
- `--city`
- `--bbox`
- `--data-dir`

```bash
# 城市名：区位+选址
geoclaw-openai run --case native_cases --city "武汉市"

# bbox：区位分析
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 本地目录：选址分析
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download
```

## 9. Mobility（轨迹）分析（Track-Intel）

轨迹处理链路融合 Track-Intel（MIE Lab）：
- 来源：<https://github.com/mie-lab/trackintel>

运行示例：

```bash
python3 -m pip install --user --break-system-packages 'geoclaw-openai[network]'

geoclaw-openai network \
  --pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv \
  --out-dir data/outputs/network_trackintel_demo \
  --activity-time-threshold 5 \
  --location-epsilon 80 \
  --location-min-samples 1 \
  --location-agg-level dataset
```

主要输出：
- `od_edges.csv`
- `od_nodes.csv`
- `od_trips.csv`
- `network_summary.json`

## 10. 常用命令

```bash
geoclaw-openai --help
geoclaw-openai onboard --help
geoclaw-openai config show
geoclaw-openai config set --help
geoclaw-openai run --help
geoclaw-openai operator --help
geoclaw-openai network --help
geoclaw-openai skill -- --help
geoclaw-openai memory --help
geoclaw-openai nl --help
geoclaw-openai profile --help
geoclaw-openai update --help
```

## 11. 环境变量（AI 相关）

优先推荐通用变量：
- `GEOCLAW_AI_PROVIDER`
- `GEOCLAW_AI_BASE_URL`
- `GEOCLAW_AI_API_KEY`
- `GEOCLAW_AI_MODEL`
- `GEOCLAW_AI_TIMEOUT`
- `GEOCLAW_AI_MAX_CONTEXT_CHARS`

兼容变量（按 provider）：
- OpenAI：`GEOCLAW_OPENAI_*`
- Qwen：`GEOCLAW_QWEN_*`
- Gemini：`GEOCLAW_GEMINI_*`

Profile layers：
- `GEOCLAW_SOUL_PATH`：指定 `soul.md` 路径（可选）
- `GEOCLAW_USER_PATH`：指定 `user.md` 路径（可选）

## 12. 文档导航

- 技术参考：`docs/technical-reference-geoclaw-openai.md`
- 全量复盘：`docs/geoclaw-full-retrospective-v2.4.0.md`
- 开发指南：`docs/development-guide.md`
- 科研学习手册：`docs/scientist-learning-guide.md`
- 原生案例与 Skill：`docs/native-cases-and-skills.md`
- Skill 案例（商场选址双写法）：`docs/skill-case-mall-site-selection.md`
- Skill 编写规范：`docs/skill-authoring-spec.md`
- Skill 安全门禁：`docs/skill-security-guard.md`
- Soul/User 分层说明：`docs/soul-user-profile.md`
- CLI 安装与初始化：`docs/cli-onboard.md`
- 版本记录：`docs/release-notes.md`
- Changelog：`CHANGELOG.md`

## 13. License

详见 `LICENSE`。
