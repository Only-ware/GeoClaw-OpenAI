# GeoClaw-OpenAI Release Notes

## v3.1.0 (2026-03-08)

主要迭代：

1. 本地大模型支持（Ollama）
   - 新增 provider：`ollama`。
   - 默认端点：`http://127.0.0.1:11434/v1`。
   - 默认模型：`llama3.1:8b`。
   - `onboard` / `config set` 均支持 `--ai-provider ollama`。
   - 本地模式可无真实 API Key（自动占位 key 兼容配置检查）。

2. Profile 对话更新机制（可控写入）
   - 新增命令：`geoclaw-openai profile evolve`。
   - 支持：`--target user|soul|both`、`--summary`、`--set`、`--add`。
   - `soul` 更新必须显式 `--allow-soul`。
   - 安全/执行边界相关 key 在代码层强制锁定，无法通过对话改写。

3. 自然语言路由增强
   - 新增 profile 更新意图识别。
   - 可将“更新 user.md/soul.md 偏好”的自然语言请求路由到 `profile evolve`。

4. 测试与文档同步
   - 新增 Ollama 与 profile-evolve 相关单元测试。
   - README、技术参考、工程说明书同步更新为 v3.1.0。

## v3.0.0-maintenance (2026-03-08)

主要迭代：

1. NL 路由通用性修复
   - `run` 意图的 SRE 路由兼容策略收紧为 `run/skill`，阻断误改写到 `operator/network`。
   - 新增 NL 显式参数保留层，SRE 路由后强制保留用户明确输入：
     - `run`：`city/bbox/data-dir/top-n/with-maps/...`
     - `network`：`pfs-csv/out-dir/...`
     - `operator`：`algorithm + param/param-json` 列表

2. data 目录跟踪策略调整
   - `.gitignore` 取消对 `data/` 的忽略，便于新用户直接获取学习样例与可复现实验资产。

3. 复杂自然语言端到端测试套件
   - 新增：`scripts/e2e_complex_nl_suite.sh`
   - 覆盖 4 组复杂场景（商场选址、本地目录区位、轨迹 network、operator）。

4. 文档更新
   - README、技术参考、开发指南、新手教程同步更新。
   - 工程说明书 `GeoClaw-OpenAI_工程说明书.docx/.pdf` 重新生成。

## v3.0.0 (2026-03-08)

主要迭代：

1. 版本升级
   - 包版本与运行时版本升级为 `3.0.0`。

2. SRE 3.0 重构阶段收口（Milestone A-F）
   - 规则与模板配置化（`reasoning/rules/*.yaml`、`reasoning/templates/*.yaml`）。
   - `execution_plan` 路由安全校验（白名单、命令形状、跨意图阻断）。
   - 高级推理字段（`reasoning_mode`、`uncertainty_score`、`sensitivity_hints`）及报告输出。
   - 外部 LLM reasoner 支持配置化模板、结构化校验重试、strict/non-strict 降级策略。
   - 外部错误详情脱敏，避免 API key 片段进入结果。

3. 端到端询问并输出报告（NL + SRE）
   - `nl` 新增：
     - `--sre-report-out`：将 SRE 推理报告直接写入 `data/outputs`。
     - `--sre-print-report`：在终端输出 Markdown 报告。
   - 形成“自然语言询问 -> SRE 推理 -> 报告输出”的端到端链路。

4. day-run 扩展与回归收敛
   - `scripts/day_run.sh` 扩展为 11 步回归矩阵：
     - `run`（native + advanced）
     - `skill`（location + site）
     - `reasoning` 报告
     - `nl --use-sre` 报告
     - `memory` 冒烟
   - 固定校验产物新增：
     - `data/outputs/reasoning/day_run_reasoning.md`
     - `data/outputs/reasoning/day_run_nl_e2e_report.md`

5. 文档与工程说明书更新
   - README、docs 与技术说明同步到 `v3.0.0`。
   - 工程说明书 `GeoClaw-OpenAI_工程说明书.docx/.pdf` 重新生成并纳入本次发布。

## v2.4.0 (2026-03-08)

主要迭代：

1. 版本升级
   - 包版本与运行时版本升级为 `2.4.0`。

2. Soul/User 双层个性化架构
   - 新增 `soul.md`（系统身份、地理推理原则、执行边界）。
   - 新增 `user.md`（用户长期画像、偏好、输出习惯）。
   - 会话初始化自动加载并解析为结构化对象。

3. 模块接入落地（planner/router/report/memory）
   - planner（`nl/intent.py`）消费 profile 上下文，增强命令规划与解释原因。
   - tool router（`cli nl` / `skill runner`）消费执行层级与用户偏好，支持注册 Skill 优先路由。
   - report generator（`run_qgis_pipeline.py`）在 `pipeline_report.json` 写入 profile 元信息。
   - memory manager（`memory/store.py`）新增 profile 快照并在复盘建议中引用长期偏好。

4. Profile CLI 与用户引导
   - 新增 `geoclaw-openai profile init`。
   - 新增 `geoclaw-openai profile show`。
   - `onboard` 后自动确保 `~/.geoclaw-openai/soul.md` 与 `user.md` 存在。

5. 文档与工程说明书更新
   - README、docs 全量同步到 v2.4.0。
   - 工程说明书 `GeoClaw-OpenAI_工程说明书.docx/.pdf` 重新生成并纳入本次发布。

## v2.3.0 (2026-03-07)

主要迭代：

1. 自动上下文压缩
   - 新增 `src/geoclaw_qgis/ai/context.py`。
   - AI 输入超过阈值时自动压缩（保留头部、关键片段、尾部）。
   - 通过 `GEOCLAW_AI_MAX_CONTEXT_CHARS` 调整压缩阈值。

2. 多 AI Provider 正式支持
   - `openai`、`qwen`、`gemini` 三 provider 统一接入。
   - `onboard` 与 `config set` 均支持 provider/base_url/model/key 配置。
   - 兼容 provider 专属环境变量（`GEOCLAW_OPENAI_*`、`GEOCLAW_QWEN_*`、`GEOCLAW_GEMINI_*`）。

3. Memory 增强
   - 新增短期 memory 归档：`geoclaw-openai memory archive`。
   - 新增向量检索：`geoclaw-openai memory search`（`short/long/archive/all`）。
   - Memory 路径结构升级：新增 `~/.geoclaw-openai/memory/archive/short/`。

4. 输出安全机制增强
   - 新增 `security/output_guard.py`。
   - 输出路径强制在 `data/outputs`。
   - 禁止输入输出同路径，防止 in-place 覆盖输入文件。

5. 版本升级
   - 包版本与运行时版本升级为 `2.3.0`。

## v2.1.0 (2026-03-07)

主要迭代：

1. 轨迹数据处理模块落地
   - 新增轨迹测试数据目录：`data/examples/trajectory/`。
   - 新增测试数据：`trackintel_demo_pfs.csv`（positionfixes 示例）。

2. 复杂网络分析能力增强
   - `geoclaw-openai network` 支持基于轨迹数据生成 OD 网络与复杂网络指标。
   - 导出结果包含：`od_edges.csv`、`od_nodes.csv`、`od_trips.csv`、`network_summary.json`。
   - 新增可复现 demo 脚本：`scripts/run_trackintel_network_demo.sh`。

3. 算法来源标注
   - 明确说明轨迹处理算法来源于 [Track-Intel（MIE Lab）](https://github.com/mie-lab/trackintel)。

## v2.0.0 (2026-03-07)

主要迭代：

1. 自然语言操作引入
   - 新增 `geoclaw-openai nl "<query>"`，支持自然语言到 CLI 计划解析。
   - 默认预览，`--execute` 可直接执行。

2. 任务记忆闭环增强
   - 每次任务自动写入短期 memory。
   - 任务完成后自动复盘并写入长期 memory。
   - 支持手动复盘：`geoclaw-openai memory review --task-id ...`。

3. 自更新能力工程化
   - 新增 `geoclaw-openai update --check-only` 和 `geoclaw-openai update`。

## v1.1.0 (2026-03-07)

主要迭代：

1. 引入任务记忆系统
   - 短期 memory：`~/.geoclaw-openai/memory/short/`
   - 长期 memory：`~/.geoclaw-openai/memory/long_term.jsonl`

2. 增加自更新能力
   - 可检测远端更新并拉取最新代码。

## v1.0.0 (2026-03-07)

稳定发布说明：

1. 形成完整 GIS 分析闭环
   - 支持城市名 / bbox / 本地目录三种输入。
   - 支持区位分析、选址分析、综合案例与专题出图。

2. 空间分析能力增强
   - 新增栅格与矢量 API。
   - 新增单算法灵活运行入口 `geoclaw-openai operator`。
