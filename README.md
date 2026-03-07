# GeoClaw-OpenAI (v2.3.0)

GeoClaw-OpenAI 是一个基于 `QGIS Processing (qgis_process)` 的空间分析与制图工具链，面向科研和工程团队，支持从数据获取、分析建模、结果制图到 AI 解释的完整流程。

机构：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. v2.3 新增能力（重点）

本次版本重点新增以下能力：

1. 自动上下文压缩
- AI 输入上下文过长时自动压缩（保留头部、关键词片段、尾部）。
- 默认自动触发，不需要手动开启。
- 可通过环境变量 `GEOCLAW_AI_MAX_CONTEXT_CHARS` 调整阈值。

2. 多 Provider 支持
- 支持 `openai`、`qwen`、`gemini`。
- `onboard` 可直接设置 provider；后续可通过 `config set` 切换 provider 和模型。

3. Memory 存档与向量检索
- 新增 `memory archive`：归档短期记忆。
- 新增 `memory search`：基于向量检索历史记忆（short/long/archive/all）。

4. 安全写入机制
- 输出目录固定在 `data/outputs` 下。
- 阻止 in-place 输出覆盖输入文件。
- 已接入 `run`/`operator`/`network`/pipeline 主链路。

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
  --ai-model "gpt-4.1-mini"

# Qwen
geoclaw-openai onboard --non-interactive \
  --ai-provider qwen \
  --api-key "<QWEN_KEY>" \
  --ai-model "qwen-plus"

# Gemini
geoclaw-openai onboard --non-interactive \
  --ai-provider gemini \
  --api-key "<GEMINI_KEY>" \
  --ai-model "gemini-2.0-flash"
```

## 4. 后期切换模型/Provider（无需重装）

```bash
# 查看当前配置
geoclaw-openai config show

# 切换 provider + 模型
geoclaw-openai config set --ai-provider openai --ai-model gpt-4.1-mini
geoclaw-openai config set --ai-provider qwen --ai-model qwen-plus
geoclaw-openai config set --ai-provider gemini --ai-model gemini-2.0-flash

# 可同时改 base_url / key
geoclaw-openai config set --ai-provider gemini --ai-base-url "https://generativelanguage.googleapis.com/v1beta/openai" --api-key "<GEMINI_KEY>"
```

## 5. 自然语言入口

```bash
# 默认预览
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"

# 直接执行
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute
```

当前 NL 覆盖：`run` / `operator` / `network` / `skill` / `memory` / `update`。

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

## 12. 文档导航

- 技术参考：`docs/technical-reference-geoclaw-openai.md`
- 全量复盘：`docs/geoclaw-full-retrospective-v2.1.0.md`
- 开发指南：`docs/development-guide.md`
- 科研学习手册：`docs/scientist-learning-guide.md`
- 原生案例与 Skill：`docs/native-cases-and-skills.md`
- CLI 安装与初始化：`docs/cli-onboard.md`
- 版本记录：`docs/release-notes.md`
- Changelog：`CHANGELOG.md`

## 13. License

详见 `LICENSE`。
