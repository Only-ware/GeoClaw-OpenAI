# GeoClaw-OpenAI (v3.2.2)

> 安全声明：建议在沙盒或隔离开发环境中运行 GeoClaw-OpenAI，避免在主力生产机直接执行本地工具命令。

GeoClaw-OpenAI 是一个基于 `QGIS Processing (qgis_process)` 的空间分析与制图工具链，面向科研和工程团队，支持从数据获取、分析建模、结果制图到 AI 解释的完整流程。

机构：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 快速入口（持续维护）

- 新手教程（安装/配置/一条命令运行）：[`docs/beginner-quickstart.md`](docs/beginner-quickstart.md)
- 可直接用分析 Skill 快速上手：[`docs/analysis-skills-quickstart.md`](docs/analysis-skills-quickstart.md)
- 商场选址端到端案例（前5候选点）：[`data/examples/site_selection/wuhan_mall_top5/README.md`](data/examples/site_selection/wuhan_mall_top5/README.md)
- 聊天模式端到端案例（景德镇前5商场候选点）：[`data/examples/chat_mode/jingdezhen_mall_top5/README.md`](data/examples/chat_mode/jingdezhen_mall_top5/README.md)
- Web 团队试用版（会话管理/重试/执行状态/输出链接）：`geoclaw-openai web --open-browser`
- 10轮对话易读报告（Q/A/过程/输出路径）：[`examples/chat/dialogue_suite_10_rounds_easy_read_20260310.md`](examples/chat/dialogue_suite_10_rounds_easy_read_20260310.md)
- 20轮复杂场景对话易读报告：[`examples/chat/dialogue_suite_20_rounds_easy_read_20260310.md`](examples/chat/dialogue_suite_20_rounds_easy_read_20260310.md)
- 30轮连续闲聊测试报告（不触发任务执行）：[`examples/chat/dialogue_suite_30_rounds_chitchat_20260310.md`](examples/chat/dialogue_suite_30_rounds_chitchat_20260310.md)
- 复杂自然语言端到端回归：`bash scripts/e2e_complex_nl_suite.sh`

> 说明：新手教程是持续维护文档，后续每次 CLI 或参数行为变更都会同步更新该文档。

## 1. v3.2.2 新增能力（重点）

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

10. Onboard 密钥输入体验增强（新增）
- `onboard` 交互输入 API Key 时采用明文可见输入，便于核对长 key。
- 再次配置时显示脱敏提示（仅展示开头和结尾字符），例如 `sk-1***9XYZ`。

11. Chat 执行链路增强（新增）
- `geoclaw-openai chat --execute` 可将可执行请求自动委派到 NL/Run 工作流。
- 修复显式输入源的错误路由风险，显式 `--city/--bbox/--data-dir` 优先保持原始研究区域。
- 新增景德镇端到端用户案例，输出聊天过程、推理报告和 Top5 结果表。

12. 城市/区域通用化与坐标输出（新增）
- NL 优先识别研究城市/区域，不再对特定城市做硬编码特判。
- `site_selection`/`mall_site_selection_qgis` 输出新增 `LONGITUDE/LATITUDE` 字段（WGS84）。
- `run` 执行会根据研究区域自动推断 `target_crs`（UTM 分区），提升跨城市适配性。

13. 新增可直接用分析 Skill 指南（新增）
- 新增 `docs/analysis-skills-quickstart.md`，面向新手提供“可直接运行”的分析 Skill 清单。
- 覆盖 `pipeline/ai/builtin` 三类 Skill 的最短命令、参数规则与输出定位方法。

14. OpenClaw Skill 兼容接入（新增）
- 新增 `skill-registry import-openclaw`，支持导入 OpenClaw 风格 JSON/YAML skill 描述。
- 导入后仍执行 GeoClaw 安全评估与注册确认流程。

15. Chat 连续会话 + Profile 热更新（新增）
- 新增 `chat --interactive --session-id <id>` 连续会话模式，持久化多轮上下文。
- Chat 消息命中 profile 意图时可直接更新 `user.md/soul.md` 并热加载。
- `chat --execute` 下可在聊天中触发工作流执行（run/operator/network/skill 等）。

16. GeoClaw 身份定义防答偏（新增）
- 新增固定身份定义文件：`src/geoclaw_qgis/identity.py`。
- 明确 GeoClaw-OpenAI 是 GIS/GeoAI 空间分析智能体，不是 Clawpack 海啸 GeoClaw。
- 固定输出“是什么、谁开发、主要功能、参考文件”统一口径。

17. 多轮对话回归与易读报告（新增）
- 新增 `scripts/run_dialogue_10_rounds.sh`、`scripts/run_dialogue_15_rounds.sh`、`scripts/run_dialogue_20_rounds.sh`。
- 新增 `scripts/run_dialogue_30_chitchat.sh`（30轮连续闲聊，强校验 `intent=chat` 且无执行链路）。
- 产出可直接阅读的对话报告：`examples/chat/dialogue_suite_*_easy_read_*.md`。

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

# QGIS 矢量分析 Skill
geoclaw-openai skill -- --skill vector_basics_qgis --set raw_dir=data/raw/wuhan_osm --set out_dir=data/outputs/demo_vector

# QGIS 栅格分析 Skill
geoclaw-openai skill -- --skill raster_basics_qgis --set raw_dir=data/raw/wuhan_osm --set out_dir=data/outputs/demo_raster

# QGIS 通用算子 Skill（builtin）
geoclaw-openai skill -- --skill qgis_operator_skill --args "--algorithm native:buffer --params-file configs/examples/operator_buffer_params.yaml"

# 轨迹网络 Skill（builtin）
geoclaw-openai skill -- --skill network_trackintel_skill --args "--pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv --out-dir data/outputs/network_trackintel_skill_demo"

# 注册前安全评估
geoclaw-openai skill-registry assess --spec-file configs/examples/high_risk_skill_injection.json

# 注册（需要确认）
geoclaw-openai skill-registry register --spec-file configs/examples/new_skill.json --confirm

# OpenClaw Skill 兼容导入（先 dry-run）
geoclaw-openai skill-registry import-openclaw --spec-file configs/examples/openclaw_skill_example.yaml --id-prefix oc_ --dry-run

# OpenClaw Skill 兼容导入并注册
geoclaw-openai skill-registry import-openclaw --spec-file configs/examples/openclaw_skill_example.yaml --id-prefix oc_ --confirm
```

## 2. 核心能力总览

- 区位分析、选址分析、武汉综合案例（含聚类）
- 选址候选点输出经纬度（`LONGITUDE/LATITUDE`）便于直接落图与复核
- 批量专题图导出（PNG）+ QGIS 工程文件（QGZ）
- 自然语言操作（`geoclaw-openai nl`）
- 闲聊模式（`geoclaw-openai chat`）+ 连续多轮会话（`--interactive`）+ 无法直接解决时的建议方案
- Web 前端试用版（`geoclaw-openai web`）
  - 会话管理（新建/切换/删除）
  - 错误提示与一键重试
  - 执行状态显示（是否触发工具、返回码、意图）
  - 报告/输出文件链接展示（`data/outputs`、`examples`）
- 本地工具调用（`geoclaw-openai local --cmd ...`）
- 空间推理引擎（`geoclaw-openai reasoning` + `nl --use-sre`）
- Skill 扩展（`pipeline` / `ai` / `builtin`）
- OpenClaw 风格 Skill 兼容导入（`skill-registry import-openclaw`）
- Memory 任务闭环（短期 + 长期复盘）
- Mobility（轨迹）分析（Track-Intel 融合）
- 自更新能力（`geoclaw-openai update`）

## 3. 安装与初始化（新手完整流程）

### 3.1 从 GitHub 克隆项目

```bash
# 1) 克隆仓库
git clone https://github.com/whuyao/GeoClaw-OpenAI.git

# 2) 进入项目目录
cd GeoClaw-OpenAI
```

如果你已经克隆过，可先更新到最新代码：

```bash
cd GeoClaw-OpenAI
git pull origin main
```

### 3.2 检查本地环境

```bash
bash scripts/check_local_env.sh
```

该脚本会检查 `python3`、`qgis_process` 等关键依赖是否可用。

### 3.3 安装 CLI 命令

```bash
bash scripts/install_geoclaw_openai.sh
```

安装后验证：

```bash
geoclaw-openai --help
```

如果提示 `command not found`，通常是用户级 Python bin 不在 PATH。可执行：

```bash
# macOS/Linux 常见修复
export PATH="$HOME/Library/Python/3.14/bin:$PATH"
# 或（部分系统）
export PATH="$HOME/.local/bin:$PATH"
```

你也可以把上面 `export` 写进 `~/.zshrc` 或 `~/.bashrc` 后重新打开终端。

### 3.4 首次配置（onboard）

```bash
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
```

`onboard` 会引导你设置：
- AI Provider（OpenAI / Qwen / Gemini / Ollama）
- API Key（Ollama 本地模式可留空；输入时为可见模式，重配时会显示脱敏提示）
- AI Base URL / Model
- 默认 BBOX
- 默认工作目录、技能注册表路径
- `qgis_process` 路径

### 3.5 新手第一条验证命令

```bash
geoclaw-openai config show
geoclaw-openai skill -- --list
geoclaw-openai nl "武汉最适合建商场的前5个地点，输出结果和简要解释"

# 启动 Web 试用版（默认 http://127.0.0.1:8765）
geoclaw-openai web --open-browser
```

看到 `command_preview`/`cli_args` 即表示安装与配置成功（未执行分析）。

Web 试用版说明：
- 页面顶部包含版权声明与 GitHub 地址。
- 默认用于 3-5 天团队内部试用验证。
- `chat` 默认 AI-first；如未完成 `onboard` 配置 API key，Web 会返回错误并支持重试。

### 3.6 Windows（PowerShell）安装流程 + QGIS 安装

适用人群：Windows 新手用户，不熟悉 Python/GIS 环境配置。

先准备两个基础工具：
1. Git（用于 `git clone`）
2. Python 3.10+（安装时勾选 “Add python.exe to PATH”）

#### 3.6.1 先安装 QGIS（必须）

1. 打开 QGIS 官网下载页：<https://qgis.org/download/>
2. 选择 Windows 版本，优先安装 LTR（长期支持版）或最新稳定版。
3. 按默认选项安装完成后，确认以下文件存在（版本号目录可能不同）：
   - `C:\Program Files\QGIS <version>\bin\qgis_process.exe`

在 PowerShell 里可自动查找 `qgis_process.exe`：

```powershell
Get-ChildItem "C:\Program Files\QGIS*" -Recurse -Filter qgis_process.exe -ErrorAction SilentlyContinue |
  Select-Object -First 1 -ExpandProperty FullName
```

如果命令有返回路径，说明 QGIS 核心工具已可用。

#### 3.6.2 PowerShell 从仓库安装 GeoClaw

```powershell
# 1) 克隆仓库
git clone https://github.com/whuyao/GeoClaw-OpenAI.git
cd GeoClaw-OpenAI

# 2) 安装 GeoClaw（用户级）
py -3 -m pip install --user -e .

# 3) 把 Python Scripts 目录加入当前 PowerShell PATH（临时）
$USER_BASE = py -3 -m site --user-base
$SCRIPTS = Join-Path $USER_BASE "Scripts"
$env:Path = "$SCRIPTS;$env:Path"

# 4) 验证 CLI
geoclaw-openai --help
```

如需永久写入用户 PATH（仅需一次）：

```powershell
[Environment]::SetEnvironmentVariable("Path", "$SCRIPTS;$([Environment]::GetEnvironmentVariable('Path','User'))", "User")
```

#### 3.6.3 Windows 上执行 onboard

```powershell
# 将下面路径替换为你机器实际 qgis_process 路径
geoclaw-openai onboard --qgis-process "C:\Program Files\QGIS 3.40.0\bin\qgis_process.exe"
```

Windows 下不需要执行 `source ~/.geoclaw-openai/env.sh`。  
`onboard` 写入的配置会由 GeoClaw CLI 自动读取。

### 3.7 卸载与重装

推荐先用 `--dry-run` 预览动作，再执行真实操作。

```bash
# CLI 卸载（默认只卸载命令与包，不删配置）
geoclaw-openai uninstall --dry-run --yes
geoclaw-openai uninstall --yes

# 连同本地配置/记忆一起清理
geoclaw-openai uninstall --purge-home --yes

# CLI 重装（卸载 + 安装）
geoclaw-openai reinstall --dry-run --yes
geoclaw-openai reinstall --yes

# 跳过卸载，仅重新安装当前工作区 editable 包
geoclaw-openai reinstall --skip-uninstall --yes
```

也可直接使用脚本（在仓库根目录）：

```bash
bash scripts/uninstall_geoclaw_openai.sh --dry-run
bash scripts/uninstall_geoclaw_openai.sh --purge-home

bash scripts/reinstall_geoclaw_openai.sh --dry-run
bash scripts/reinstall_geoclaw_openai.sh
```

#### 3.6.4 Windows 快速自检

```powershell
geoclaw-openai config show
geoclaw-openai skill -- --list
geoclaw-openai nl "武汉最适合建商场的前5个地点，输出结果和简要解释"
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

## 4.1 可用模型名称（2026-03-09 已核验）

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

## 4.2 本地模型（Ollama）完整配置

如果你希望完全本地运行模型，可按下面步骤配置：

```bash
# 1) 安装 Ollama（macOS 示例）
brew install ollama

# 2) 启动 Ollama 服务（保持后台运行）
ollama serve

# 3) 拉取一个本地模型
ollama pull llama3.1:8b

# 4) 接入 GeoClaw
geoclaw-openai onboard --non-interactive \
  --ai-provider ollama \
  --ai-base-url "http://127.0.0.1:11434/v1" \
  --ai-model "llama3.1:8b"
source ~/.geoclaw-openai/env.sh

# 5) 验证 Ollama 服务是否可用
curl http://127.0.0.1:11434/api/tags

# 6) 验证 GeoClaw 当前 provider
geoclaw-openai config show
```

常见问题排查：
- `Connection refused`：先确认 `ollama serve` 正在运行。
- 模型不存在：先执行 `ollama pull <model_name>`。
- 端口被改动：把 `--ai-base-url` 改成你的实际地址，例如 `http://127.0.0.1:11435/v1`。
- 需要切换回云端模型：执行 `geoclaw-openai config set --ai-provider openai|qwen|gemini ...`。

## 5. 自然语言入口

AI 默认策略（v3.2.2）：
- `chat`：强制 AI 响应（默认/推荐 `--with-ai`）。
- `nl + --use-sre` 与 `reasoning`：默认 `reasoner-mode=auto`，优先尝试外部 AI 推理，失败再按安全策略降级。
- `skill`：默认尝试 AI 总结（可用 `--no-ai` 临时关闭）。

```bash
# 新手一条命令（无需写 Python）：询问并直接执行，输出前5商场候选点 + SRE 报告
geoclaw-openai nl "武汉最适合建商场的前5个地点，输出结果和简要解释" \
  --use-sre \
  --sre-reasoner-mode auto \
  --sre-report-out data/outputs/reasoning/wuhan_mall_top5_report.md \
  --execute

# 默认预览
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"

# 直接执行
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute

# 端到端：自然语言 -> SRE -> 报告输出
geoclaw-openai nl "商场选址分析，优先可复现QGIS流程" \
  --use-sre \
  --sre-reasoner-mode auto \
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

当前 NL 覆盖：`run` / `operator` / `network` / `skill` / `memory` / `update` / `profile` / `chat` / `local`。
在 v3.2.2 中，NL 规划会读取 `soul.md/user.md`，并按“研究区域优先”执行路由；当用户显式给出 `city/bbox/data-dir` 时优先保持原始输入范围。  
同时支持通过自然语言触发 profile 更新（会路由到 `profile evolve`）。
启用 SRE 时可用：
- `--sre-report-out`：输出 Markdown 推理报告（必须在 `data/outputs` 下）
- `--sre-print-report`：输出 JSON 后打印报告正文
- 通用路由约束：当用户在自然语言中显式给出关键参数（如 `run` 的 `city/bbox/data-dir/top-n`、`network` 的 `out-dir`、`operator` 的参数列表）时，CLI 会在 SRE 之后执行参数保留，避免错误改写导致的路由偏移。

闲聊与建议模式：

说明：`chat` 模式默认强制使用 AI（`--with-ai`）；普通运行不再支持 `--no-ai`。

```bash
# 直接闲聊（AI 必选）
geoclaw-openai chat --message "你好，给我一个今天的分析计划"

# 通过 NL 自动进入闲聊模式
geoclaw-openai nl "你好，我们先聊聊需求"

# 当问题暂时无法解决时，返回可执行建议
geoclaw-openai chat --message "我运行失败了，下一步怎么排查？" --with-ai

# 连续多轮聊天（会话持久化）
geoclaw-openai chat --interactive --session-id research_demo

# 单轮聊天也可复用历史上下文
geoclaw-openai chat --session-id research_demo --message "继续刚才的话题，给我下一步执行命令"

# 在聊天中直接更新 profile（自动热加载）
geoclaw-openai chat --message "请根据这次对话更新user.md偏好，偏好英文并详细" --with-ai

# 在聊天中触发工作流
geoclaw-openai chat --message "请用武汉市做商场选址前5个并输出报告" --execute --use-sre
```

连续对话模式（推荐新手先用）：

```bash
# 1) 进入连续对话（创建新会话）
geoclaw-openai chat --interactive --session-id my_first_chat --new-session

# 2) 在终端里持续输入问题；输入 exit / quit / 退出 可结束会话

# 3) 之后可继续同一会话（保留上下文）
geoclaw-openai chat --session-id my_first_chat --message "继续上一次对话"
```

会话持久化路径：
- `~/.geoclaw-openai/chat/sessions/<session_id>.json`

本地工具调用：

```bash
# 预览（NL）
geoclaw-openai nl "执行命令: ls -la"

# 直接执行本地命令
geoclaw-openai local --cmd "ls -la"
geoclaw-openai local --cmd "qgis_process --version" --timeout 30
```

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
geoclaw-openai chat --help
geoclaw-openai local --help
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
- 可直接用分析 Skill 快速上手：`docs/analysis-skills-quickstart.md`
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

## 14. 验证状态（2026-03-10）

当前版本 `v3.2.2` 已通过本地回归：

- 单元测试：`python3 -m unittest discover -s src/geoclaw_qgis/tests`（118/118 通过）
- OpenClaw 兼容导入冒烟：`geoclaw-openai skill-registry import-openclaw --spec-file configs/examples/openclaw_skill_example.yaml --id-prefix oc_ --dry-run`（success）
- 连续聊天冒烟：`geoclaw-openai chat --interactive --session-id demo_chat --new-session --with-ai`（success，已落盘会话）
- 全链路日常回归：`bash scripts/day_run.sh`（success）
- 复杂自然语言端到端回归：`bash scripts/e2e_complex_nl_suite.sh`（4/4 场景 success）
- 10轮对话回归：`bash scripts/run_dialogue_10_rounds.sh`（PASS=10, FAIL=0）
- 15轮对话回归：`bash scripts/run_dialogue_15_rounds.sh`（PASS=15, FAIL=0）
- 20轮复杂场景回归：`bash scripts/run_dialogue_20_rounds.sh`（PASS=20, FAIL=0）
- 30轮连续闲聊回归（无任务触发）：`bash scripts/run_dialogue_30_chitchat.sh`（PASS=30, FAIL=0）
- 30轮闲聊易读报告：`examples/chat/dialogue_suite_30_rounds_chitchat_20260310.md`
- 聊天端到端案例：`chat --execute`（景德镇商场 Top5）成功生成过程与报告：
  - `data/examples/chat_mode/jingdezhen_mall_top5/chat_process.json`
  - `data/examples/chat_mode/jingdezhen_mall_top5/jingdezhen_mall_top5_report.md`

`day_run.sh` 当前覆盖：
- run：`native_cases` + `wuhan_advanced`
- skill：`location_analysis` + `site_selection`
- reasoning：`--reasoner-mode auto` + 报告输出
- nl：`--use-sre --sre-reasoner-mode auto --sre-report-out ...`
- memory：`status/short/long/search` 冒烟

## 15. License

详见 `LICENSE`。
