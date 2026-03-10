# GeoClaw CLI 安装与 Onboard（v3.2.0）

机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

新手建议先读：
- `docs/beginner-quickstart.md`（最短路径）
- `README.md` 的「3. 安装与初始化（新手完整流程）」（含 Windows + QGIS）

## 1) 安装

```bash
bash scripts/install_geoclaw_openai.sh
```

安装后可使用命令：`geoclaw-openai`。

若你是 Windows 用户，请优先参考 README 中的 PowerShell 安装段落，并先安装 QGIS。

## 2) 首次初始化（推荐）

```bash
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
```

初始化会写入：

- `~/.geoclaw-openai/config.json`
- `~/.geoclaw-openai/.env`
- `~/.geoclaw-openai/env.sh`
- `~/.geoclaw-openai/soul.md`
- `~/.geoclaw-openai/user.md`

交互输入说明（v3.2.0）：
- API Key 输入为可见模式，便于核对长 key。
- 若已配置旧 key，提示中会展示脱敏片段（仅开头+结尾），回车可保持原值。

## 3) 非交互初始化

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

# Ollama（本地模型，默认无需真实 API key）
geoclaw-openai onboard --non-interactive \
  --ai-provider ollama \
  --ai-base-url "http://127.0.0.1:11434/v1" \
  --ai-model "llama3.1:8b"
```

可选参数：`--ai-base-url`、`--qgis-process`、`--default-bbox`、`--registry`、`--workspace`。

## 3.1 Profile Layers（Soul/User）

```bash
# 初始化默认 soul/user
geoclaw-openai profile init

# 查看当前加载路径与摘要
geoclaw-openai profile show

# 根据对话摘要更新长期偏好（user.md）
geoclaw-openai profile evolve \
  --target user \
  --summary "偏好中文、简洁风格，优先本地模型" \
  --set preferred_language=Chinese \
  --set preferred_tone=concise \
  --add preferred_tools=Ollama,QGIS

# 更新 soul.md 的非安全字段（必须显式允许）
geoclaw-openai profile evolve \
  --target soul \
  --allow-soul \
  --summary "补充任务使命说明" \
  --set mission="Help users perform reliable and reproducible geospatial analysis."
```

说明：
- `soul.md`：系统层原则和行为边界（高优先级）。
- `user.md`：用户长期画像与偏好（软个性化层）。
- 支持环境变量覆盖路径：`GEOCLAW_SOUL_PATH`、`GEOCLAW_USER_PATH`。
- `profile evolve` 只允许更新 `soul.md` 的非安全字段；安全边界字段会被系统强制阻断。

## 4) 后续配置调整（无需重装）

```bash
# 查看当前配置
geoclaw-openai config show

# 切换 provider / 模型
geoclaw-openai config set --ai-provider openai --ai-model gpt-5.4
geoclaw-openai config set --ai-provider qwen --ai-model qwen3-max
geoclaw-openai config set --ai-provider gemini --ai-model gemini-3.1-pro-preview
geoclaw-openai config set --ai-provider ollama --ai-model llama3.1:8b

# 一并更新 API key / URL
geoclaw-openai config set \
  --ai-provider gemini \
  --ai-base-url "https://generativelanguage.googleapis.com/v1beta/openai" \
  --api-key "<GEMINI_KEY>"
```

常用模型名（2026-03-09）：

- OpenAI：`gpt-5.4`、`gpt-5.4-pro`、`gpt-5-mini`、`gpt-5-nano`
- Gemini：`gemini-3.1-pro-preview`、`gemini-3.1-flash-lite-preview`、`gemini-3-flash-preview`、`gemini-flash-latest`
- Qwen：`qwen3-max`、`qwen3.5-plus`、`qwen3.5-flash`、`qwen-plus-latest`
- Ollama：`llama3.1:8b`、`qwen2.5:7b`、`deepseek-r1:8b`（示例）

说明：`geoclaw-openai` 接受任意 provider 当前有效模型 ID，推荐先使用 `*-latest` 别名，需强复现时再固定具体版本名。

## 5) 常用命令清单

```bash
# 输入源：city / bbox / data-dir（三选一）
geoclaw-openai run --case native_cases --city "武汉市"
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download

# 单算法
geoclaw-openai operator \
  --algorithm native:buffer \
  --params-file configs/examples/operator_buffer_params.yaml

# 自然语言（默认预览）
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute
geoclaw-openai nl "商场选址分析，优先可复现工作流" --execute
geoclaw-openai nl "商场选址分析，优先可复现QGIS流程" --use-sre --sre-report-out data/outputs/reasoning/nl_e2e_report.md

# 闲聊 / 建议模式
geoclaw-openai chat --message "我运行失败了，下一步怎么排查？" --no-ai
geoclaw-openai chat --interactive --session-id onboarding_demo
geoclaw-openai chat --session-id onboarding_demo --message "继续上一次对话"
geoclaw-openai chat --message "请根据这次对话更新user.md偏好，偏好英文并详细" --no-ai

# 连续对话（新建/退出/恢复）
geoclaw-openai chat --interactive --session-id onboarding_demo --new-session
# 退出关键词：exit / quit / 退出
geoclaw-openai chat --session-id onboarding_demo --message "继续上一次对话"
# 会话文件：~/.geoclaw-openai/chat/sessions/onboarding_demo.json

# 本地工具执行
geoclaw-openai local --cmd "qgis_process --version" --timeout 30

# TrackIntel 轨迹网络
geoclaw-openai network \
  --pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv \
  --out-dir data/outputs/network_trackintel_demo

# Skill 安全评估（注册前）
geoclaw-openai skill-registry assess --spec-file configs/examples/high_risk_skill_injection.json
```

## 6) Memory（短期/长期/归档/检索）

```bash
geoclaw-openai memory status
geoclaw-openai memory short --limit 10
geoclaw-openai memory long --limit 10
geoclaw-openai memory review --task-id "<TASK_ID>" --summary "复盘总结"
geoclaw-openai memory archive --before-days 7
geoclaw-openai memory search --query "site selection" --scope all --top-k 5
```

默认路径：

- 短期：`~/.geoclaw-openai/memory/short/`
- 长期：`~/.geoclaw-openai/memory/long_term.jsonl`
- 归档：`~/.geoclaw-openai/memory/archive/short/`

## 7) 自动上下文压缩

AI 上下文超过阈值时自动压缩，不需要手动开启。

- 变量：`GEOCLAW_AI_MAX_CONTEXT_CHARS`
- 默认：`12000`

## 8) 安全策略（必须了解）

- 输出必须位于 `data/outputs` 下。
- 禁止输出覆盖输入路径（防止误删/误覆盖原始数据）。

如果输出路径不安全，`run/operator/network` 会直接报错并终止。

## 9) 自更新

```bash
# 检查是否有更新
geoclaw-openai update --check-only

# 拉取并更新（默认 origin/main）
geoclaw-openai update

# 若仓库主分支是 master，请显式指定
geoclaw-openai update --branch master
```
