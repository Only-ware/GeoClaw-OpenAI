# GeoClaw-OpenAI 技术参考（科研与团队版，v3.0.0）

更新时间：2026-03-08（Asia/Shanghai）  
机构：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 技术定位

`geoclaw-openai` 是一个以 `qgis_process` 为核心执行引擎的 GIS + AI 工程框架，提供：

- 区位分析、选址分析、综合案例
- 栅格/矢量 pipeline 执行与单算法灵活参数
- 自然语言到 CLI 的计划解析
- Skill 扩展（pipeline/ai）
- Soul/User 个性化分层（系统边界 + 用户长期偏好）
- Memory 闭环（短期、长期、归档、检索）
- TrackIntel 轨迹网络分析

## 2. 工程结构

```text
AI-Agents/
├── configs/
├── data/
│   ├── raw/
│   ├── outputs/
│   └── examples/trajectory/
├── docs/
├── pipelines/
├── scripts/
├── soul.md
├── user.md
└── src/geoclaw_qgis/
    ├── ai/
    ├── analysis/
    ├── cli/
    ├── memory/
    ├── nl/
    ├── providers/
    ├── profile/
    ├── security/
    └── skills/
```

## 3. CLI 命令域

主入口：`src/geoclaw_qgis/cli/main.py`

- 配置：`onboard`、`config show`、`config set`、`env`
- 执行：`run`、`operator`、`network`、`skill`
- profile：`profile init/show`
- 记忆：`memory status/short/long/review/archive/search`
- 智能入口：`nl`
- 更新：`update`

除 `memory` 命令外，所有命令默认记录短期 memory，并在完成后自动复盘到长期 memory。

## 4. 关键实现原理

### 4.1 run：城市名 / bbox / 本地目录

入口：`scripts/geoclaw_case_runner.py`

- `--city`：地理编码后下载 OSM 数据
- `--bbox`：按边界下载 OSM 数据
- `--data-dir`：读取本地四类 GeoJSON

输出目录固定为 `data/outputs`（安全策略）。

### 4.2 operator：单算法灵活参数

入口：`scripts/geoclaw_operator_runner.py`

参数来源可叠加：

- `--param KEY=VALUE`
- `--param-json KEY=JSON`
- `--params-file file.yaml|json`

执行前调用安全检查，拦截非法输出路径。

### 4.3 AI：多 Provider + 自动上下文压缩

入口：`src/geoclaw_qgis/ai/external_client.py`

- provider：`openai` / `qwen` / `gemini`
- 协议：OpenAI-compatible `/chat/completions`
- 长上下文自动压缩：`src/geoclaw_qgis/ai/context.py`
- 压缩阈值：`GEOCLAW_AI_MAX_CONTEXT_CHARS`（默认 `12000`）

### 4.4 Memory：短期/长期/归档/检索

入口：`src/geoclaw_qgis/memory/store.py`

- 短期：`~/.geoclaw-openai/memory/short/*.json`
- 长期：`~/.geoclaw-openai/memory/long_term.jsonl`
- 归档：`~/.geoclaw-openai/memory/archive/short/*.json`
- 检索：`memory search`（哈希向量 + 余弦相似度）

### 4.5 Soul/User 个性化分层

入口：`src/geoclaw_qgis/profile/layers.py`

- `soul.md`：系统身份、地理推理原则、执行边界（系统级高优先级）
- `user.md`：用户长期画像、偏好、协作习惯（软个性化层）
- 会话启动自动加载并解析为结构化对象，供 planner/tool-router/report/memory 统一消费

### 4.6 安全策略

入口：`src/geoclaw_qgis/security/output_guard.py`

- 输出必须位于 `data/outputs`
- 输出不得与输入路径相同
- 适用于 `run/operator/network` 主链路

### 4.7 NL：自然语言解析

入口：`src/geoclaw_qgis/nl/intent.py`

- 将自然语言请求解析为 CLI 参数计划（`NLPlan`）
- 默认预览，`--execute` 执行

### 4.8 network：TrackIntel 轨迹网络

入口：`src/geoclaw_qgis/analysis/network_ops.py`

- 输入：positionfixes CSV（用户、时间、经纬度）
- 处理：staypoints/locations/trips/OD 图
- 输出：`od_edges.csv`、`od_nodes.csv`、`od_trips.csv`、`network_summary.json`

算法来源：Track-Intel（MIE Lab）。

## 5. 配置与环境变量

推荐统一变量：

- `GEOCLAW_AI_PROVIDER`
- `GEOCLAW_AI_BASE_URL`
- `GEOCLAW_AI_API_KEY`
- `GEOCLAW_AI_MODEL`
- `GEOCLAW_AI_TIMEOUT`
- `GEOCLAW_AI_MAX_CONTEXT_CHARS`
- `GEOCLAW_SOUL_PATH`
- `GEOCLAW_USER_PATH`

兼容变量：

- OpenAI：`GEOCLAW_OPENAI_*`
- Qwen：`GEOCLAW_QWEN_*`
- Gemini：`GEOCLAW_GEMINI_*`

## 6. 核心命令示例

```bash
# 初始化
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
geoclaw-openai profile init
geoclaw-openai profile show

# 区位/选址
geoclaw-openai run --case native_cases --city "武汉市"

# 单算法
geoclaw-openai operator --algorithm native:buffer --params-file configs/examples/operator_buffer_params.yaml

# 自然语言
geoclaw-openai nl "用武汉市做选址分析，前20个，出图" --execute
geoclaw-openai nl "商场选址分析，优先可复现QGIS流程" --use-sre --sre-report-out data/outputs/reasoning/nl_e2e_report.md

# 记忆
geoclaw-openai memory archive --before-days 7
geoclaw-openai memory search --query "output guard" --scope all --top-k 5

# 更新
geoclaw-openai update --check-only
```

## 7. 测试与回归建议

- 单元测试：`python3 -m unittest discover -s src/geoclaw_qgis/tests`
- day-run：`bash scripts/day_run.sh`
  - 覆盖 `run + skill + reasoning + nl(use-sre) + memory` 回归矩阵
  - 固定校验输出包含：
    - `data/outputs/reasoning/day_run_reasoning.md`
    - `data/outputs/reasoning/day_run_nl_e2e_report.md`
- 轨迹 demo：`bash scripts/run_trackintel_network_demo.sh`

## 8. TODO（技术路线）

- TODO: 将 memory 向量检索升级为可选 embedding 后端。
- TODO: 为 NL 增加更强参数抽取与冲突消解。
- TODO: 增加大规模轨迹性能基准与可视化报告模板。
