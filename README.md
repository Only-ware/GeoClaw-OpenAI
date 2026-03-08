# GeoClaw-OpenAI (v3.1.0)

GeoClaw-OpenAI 是一个基于 `QGIS Processing (qgis_process)` 的空间分析与制图工具链，面向科研和工程团队，支持从数据获取、分析建模、结果制图到 AI 解释的完整流程。

机构：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 快速入口（持续维护）

- 新手教程（安装/配置/一条命令运行）：[`docs/beginner-quickstart.md`](docs/beginner-quickstart.md)
- 商场选址端到端案例（前5候选点）：[`data/examples/site_selection/wuhan_mall_top5/README.md`](data/examples/site_selection/wuhan_mall_top5/README.md)
- 复杂自然语言端到端回归：`bash scripts/e2e_complex_nl_suite.sh`

> 说明：新手教程是持续维护文档，后续每次 CLI 或参数行为变更都会同步更新该文档。

## 1. v3.1.0 新增能力（重点）

本次版本重点新增以下能力：

1. Soul/User 双层个性化架构（新增）
- `soul.md`：系统身份、地理推理原则、执行边界（系统级高优先级）。
- `user.md`：用户长期画像与偏好（个性化软约束，不覆盖安全边界）。
- 会话初始化自动加载并解析为结构化对象，供 planner/tool-router/report/memory 使用。

2. 空间推理引擎（Spatial Reasoning Engine, SRE）3.0（新增）
- 完成 Milestone A-F：配置化规则/模板、路由安全校验、高级推理字段、外部 reasoner 校验重试。
- 引擎链路：`planner -> router -> reasoner -> validator -> report`。
- `reasoning` 支持结构化推理输出与 Markdown 报告导出。
- `day_run` 覆盖 run/skill/reasoning/nl/memory 全链路回归。

3. 端到端询问并输出报告（新增）
- `nl` 支持 `--sre-report-out` 与 `--sre-print-report`。
- 形成“自然语言问题 -> SRE -> 报告输出”端到端流程。

4. 新增 profile CLI（增强）
- `geoclaw-openai profile init`：初始化 `~/.geoclaw-openai/soul.md` 与 `user.md`。
- `geoclaw-openai profile show`：查看当前加载路径与结构化摘要。
- `geoclaw-openai profile evolve`：按对话摘要更新 profile 覆盖层。
- `soul.md` 仅允许更新非安全字段；安全边界字段在代码层强制锁定。

5. 商场选址 Skill 双写法（延续）
- `mall_site_selection_llm`：大模型策略推理写法。
- `mall_site_selection_qgis`：QGIS Processing 可复现计算写法。

6. Skill 注册前安全门禁（延续）
- 新增 `skill-registry assess` 与 `skill-registry register`。
- 注册前自动评估风险等级；`high` 风险默认阻断。
- 注册动作必须用户确认（`--confirm` 或交互 `YES`）。

7. Skill 编写规范文档（延续）
- 新增 Skill 编写规范与评审清单。
- 新增安全门禁说明与高危样例。

8. 本地大模型与多 Provider（新增）
- 新增 `ollama` provider，默认走本地 OpenAI-compatible 端点：`http://127.0.0.1:11434/v1`。
- 默认模型可直接使用 `llama3.1:8b`，并支持用户自定义任意本地模型名。

9. 模型与运行链路同步
- 默认模型保持最新族：`gpt-5-mini`、`qwen-plus-latest`、`gemini-flash-latest`、`llama3.1:8b`。
- `day_run`、CLI 默认配置与文档示例一致。

### 1.1 新增能力简要使用

```bash
# 初始化/查看 profile layers
geoclaw-openai profile init
geoclaw-openai profile show
geoclaw-openai profile evolve --target user --summary "偏好更新" --set preferred_language=Chinese --add preferred_tools=Ollama,QGIS

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
- 空间推理引擎（`geoclaw-openai reasoning` + `nl --use-sre`）
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

# Ollama（本地，默认无需真实 API key）
geoclaw-openai onboard --non-interactive \
  --ai-provider ollama \
  --ai-base-url "http://127.0.0.1:11434/v1" \
  --ai-model "llama3.1:8b"
```

## 4. 后期切换模型/Provider（无需重装）

```bash
# 查看当前配置
geoclaw-openai config show

# 切换 provider + 模型
geoclaw-openai config set --ai-provider openai --ai-model gpt-5.4
geoclaw-openai config set --ai-provider qwen --ai-model qwen3-max
geoclaw-openai config set --ai-provider gemini --ai-model gemini-3.1-pro-preview
geoclaw-openai config set --ai-provider ollama --ai-model llama3.1:8b

# 可同时改 base_url / key
geoclaw-openai config set --ai-provider gemini --ai-base-url "https://generativelanguage.googleapis.com/v1beta/openai" --api-key "<GEMINI_KEY>"
```

> GeoClaw-OpenAI 不限制具体模型名：`--ai-model` 可填写任意 provider 当前可用的模型 ID。

## 4.1 可用模型名称（2026-03-08 已核验）

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

- Ollama（本地模型仓库）  
  来源：[Ollama Models](https://ollama.com/library)
  - `llama3.1:8b`
  - `qwen2.5:7b`
  - `deepseek-r1:8b`

建议：
- 先用 `*-latest` 别名减少文档老化。
- 追求可复现时，改用固定版本模型名。

## 5. 自然语言入口

```bash
# 新手一条命令（无需写 Python）：询问并直接执行，输出前5商场候选点 + SRE 报告
geoclaw-openai nl "武汉最适合建商场的前5个地点，输出结果和简要解释" \
  --use-sre \
  --sre-reasoner-mode deterministic \
  --sre-report-out data/outputs/reasoning/wuhan_mall_top5_report.md \
  --execute

# 默认预览
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"

# 直接执行
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute

# 端到端：自然语言 -> SRE -> 报告输出
geoclaw-openai nl "商场选址分析，优先可复现QGIS流程" \
  --use-sre \
  --sre-reasoner-mode deterministic \
  --sre-report-out data/outputs/reasoning/nl_e2e_report.md

# 直接调用空间推理引擎（SRE）
geoclaw-openai reasoning "评估武汉商场选址可达性与服务覆盖" \
  --data-dir data/raw/wuhan_osm \
  --planner-task site_selection \
  --planner-method weighted_overlay \
  --print-report
```

也可直接使用示例脚本（用于教学/演示）：

```bash
bash data/examples/site_selection/wuhan_mall_top5/run_nl_wuhan_mall_top5.sh
```

当前 NL 覆盖：`run` / `operator` / `network` / `skill` / `memory` / `update` / `profile`。
在 v3.1.0 中，NL 规划会读取 `soul.md/user.md`，并在商场选址等场景触发注册 Skill 优先路由。  
同时支持通过自然语言触发 profile 更新（会路由到 `profile evolve`）。
启用 SRE 时可用：
- `--sre-report-out`：输出 Markdown 推理报告（必须在 `data/outputs` 下）
- `--sre-print-report`：输出 JSON 后打印报告正文
- 通用路由约束：当用户在自然语言中显式给出关键参数（如 `run` 的 `city/bbox/data-dir/top-n`、`network` 的 `out-dir`、`operator` 的参数列表）时，CLI 会在 SRE 之后执行参数保留，避免错误改写导致的路由偏移。

Profile 更新示例：

```bash
# 更新 user.md 偏好（对话摘要写入覆盖层）
geoclaw-openai profile evolve \
  --target user \
  --summary "用户希望后续以中文、简洁风格回复，优先使用本地模型" \
  --set preferred_language=Chinese \
  --set preferred_tone=concise \
  --add preferred_tools=Ollama,QGIS

# 更新 soul.md 非安全字段（必须显式允许）
geoclaw-openai profile evolve \
  --target soul \
  --allow-soul \
  --summary "补充协作原则说明" \
  --set mission="Help users perform reliable and reproducible geospatial analysis."
```

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
- Ollama：`GEOCLAW_OLLAMA_*`

Profile layers：
- `GEOCLAW_SOUL_PATH`：指定 `soul.md` 路径（可选）
- `GEOCLAW_USER_PATH`：指定 `user.md` 路径（可选）

## 12. 文档导航

- 技术参考：`docs/technical-reference-geoclaw-openai.md`
- 全量复盘：`docs/geoclaw-full-retrospective-v3.0.0.md`
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

## 13. 数据目录说明

- `data/` 目录内容不再被 `.gitignore` 忽略，便于新用户直接获取学习样例、原始数据与可复现实验产物。
- 建议教学与演示优先使用 `data/examples/` 下的示例资产。

## 14. 验证状态（2026-03-08）

当前版本 `v3.1.0` 已通过本地回归：

- 单元测试：`python3 -m unittest discover -s src/geoclaw_qgis/tests`（82/82 通过）
- 全链路日常回归：`bash scripts/day_run.sh`（success）
- 复杂自然语言端到端回归：`bash scripts/e2e_complex_nl_suite.sh`（4/4 场景 success）

`day_run.sh` 当前覆盖：
- run：`native_cases` + `wuhan_advanced`
- skill：`location_analysis` + `site_selection`
- reasoning：`--reasoner-mode deterministic` + 报告输出
- nl：`--use-sre --sre-reasoner-mode deterministic --sre-report-out ...`
- memory：`status/short/long/search` 冒烟

## 15. License

详见 `LICENSE`。
