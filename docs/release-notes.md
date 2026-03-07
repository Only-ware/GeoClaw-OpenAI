# GeoClaw-OpenAI Release Notes

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
