# GeoClaw-OpenAI Release Notes

## v2.1.0 (2026-03-07)

主要迭代：

1. 轨迹数据处理模块落地
   - 新增轨迹测试数据目录：`data/examples/trajectory/`。
   - 新增测试数据：`trackintel_demo_pfs.csv`（positionfixes 示例）。

2. 复杂网络分析能力增强
   - `geoclaw-openai network` 支持基于轨迹数据生成 OD 网络与复杂网络指标。
   - 导出结果包含：`od_edges.csv`、`od_nodes.csv`、`od_trips.csv`、`network_summary.json`。
   - 新增可复现 demo 脚本：`scripts/run_trackintel_network_demo.sh`。

3. 算法来源标注与文档更新
   - 明确说明轨迹处理算法来源于 [Track-Intel（MIE Lab）](https://github.com/mie-lab/trackintel)。
   - README、CLI 文档、技术参考同步加入轨迹模块说明、示例命令与 demo 结果统计。

4. 版本升级
   - 包版本与运行时版本升级为 `2.1.0`。

## v2.0.0 (2026-03-07)

主要迭代：

1. 自然语言操作正式引入
   - 新增 `geoclaw-openai nl "<query>"`，支持自然语言到 CLI 计划解析。
   - 默认预览解析结果，`--execute` 可直接执行解析命令。
   - 覆盖 `run` / `operator` / `skill` / `memory` / `update` 常见场景。

2. 任务记忆闭环增强
   - 每次任务自动写入短期 memory。
   - 任务完成后自动复盘并写入长期 memory。
   - 支持手动复盘：`geoclaw-openai memory review --task-id ...`。

3. 自更新能力工程化
   - `geoclaw-openai update --check-only` 与 `geoclaw-openai update` 形成标准自更新入口。
   - 网络不可达时采用降级策略输出 warning，避免流程中断。

## v1.1.0 (2026-03-07)

主要迭代：

1. 引入任务记忆系统（Memory）
   - 新增短期 memory：每次 CLI 任务自动写入 `~/.geoclaw-openai/memory/short/`。
   - 新增长期 memory：任务结束后自动复盘并写入 `long_term.jsonl`。
   - 新增 `geoclaw-openai memory` 命令（`status/short/long/review`）。

2. 增加自更新能力
   - 新增 `geoclaw-openai update --check-only`，用于检测远端是否有新提交。
   - 新增 `geoclaw-openai update`，支持拉取最新代码并自动执行 editable 安装。

## v1.0.0 (2026-03-07)

稳定发布说明：

1. 形成完整 GIS 分析产品闭环
   - 支持城市名 / bbox / 本地目录三种输入方式。
   - 支持区位分析、选址分析、综合案例与专题出图。

2. 空间分析能力全面增强
   - 新增栅格与矢量操作 API（`VectorAnalysisService`、`RasterAnalysisService`）。
   - 新增单算法灵活运行入口 `geoclaw-openai operator`。
