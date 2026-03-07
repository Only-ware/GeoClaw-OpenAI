# GeoClaw-OpenAI 框架设计（v2.3.3）

## 1. 设计目标

GeoClaw-OpenAI 以 QGIS Processing 为执行底座，形成 GIS 分析、制图、AI 扩展、记忆与自然语言操作的一体化框架。

## 2. 架构分层

### 2.1 CLI 编排层

入口：`src/geoclaw_qgis/cli/main.py`

命令域：

- `onboard/config/env`
- `run/operator/network/skill`
- `memory`
- `nl`
- `update`

### 2.2 任务记忆层

组件：`src/geoclaw_qgis/memory/`

- 短期 memory：记录每次任务输入参数、状态、错误
- 长期 memory：自动复盘结果
- 归档机制：短期任务按时间迁移到 archive
- 检索机制：基于哈希向量的相似度检索

### 2.3 分析执行层

- Pipeline 执行：`scripts/run_qgis_pipeline.py`
- 单算法执行：`scripts/geoclaw_operator_runner.py`
- 原生案例执行：`scripts/geoclaw_case_runner.py`
- 轨迹网络执行：`src/geoclaw_qgis/analysis/network_ops.py`

### 2.4 AI 扩展层

组件：`src/geoclaw_qgis/ai/`

- 多 provider：OpenAI / Qwen / Gemini
- 协议：OpenAI-compatible chat completions
- 自动上下文压缩：长输入自动摘要保留关键信息

### 2.5 安全控制层

组件：`src/geoclaw_qgis/security/output_guard.py`

策略：

- 强制输出路径位于 `data/outputs`
- 禁止输入输出同路径（防止覆盖/删除输入）

## 3. 典型流程

1. 用户通过 CLI 或 `nl` 发起任务。
2. CLI 记录短期 memory（start_task）。
3. 业务模块执行（run/operator/network/skill/update）。
4. CLI 写入任务结束状态并自动复盘到长期 memory。
5. 结果输出在 `data/outputs` 或 memory 目录。

## 4. 扩展策略

- 新案例：新增 pipeline + 可选 skill 注册
- 新 AI provider：扩展 `ExternalAIConfig.from_env`
- 新安全策略：扩展 `validate_output_targets`
- 新 NL 意图：扩展 `src/geoclaw_qgis/nl/intent.py`

## 5. 工程约束

- 输出目录约束优先于灵活性
- memory 不影响主流程（memory 异常只告警，不阻塞业务命令）
- 网络相关能力（TrackIntel）采用可选依赖机制

## 6. TODO（架构）

- TODO: 增加 provider 级限流与重试策略。
- TODO: 将 memory 检索升级为可插拔向量后端。
- TODO: 引入 pipeline schema 静态校验（参数类型、引用检查）。
