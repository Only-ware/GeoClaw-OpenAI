# GeoClaw-OpenAI 框架设计（v3.1.0）

## 1. 设计目标

GeoClaw-OpenAI 以 QGIS Processing 为执行底座，形成 GIS 分析、制图、AI 扩展、记忆与自然语言操作的一体化框架。
v3.1.0 引入 `soul.md + user.md` 双层个性化机制，作为系统行为与用户偏好的统一输入。

## 2. 架构分层

### 2.1 CLI 编排层

入口：`src/geoclaw_qgis/cli/main.py`

命令域：

- `onboard/config/env`
- `run/operator/network/skill`
- `profile`
- `memory`
- `nl`
- `update`

### 2.2 Soul/User Profile 层

组件：`src/geoclaw_qgis/profile/layers.py`

- `soul.md`：系统身份、推理原则、执行边界（高优先级）
- `user.md`：用户画像、长期偏好、输出习惯（软偏好层）
- 会话初始化自动加载，解析为结构化对象并注入：
  - planner（NL 计划）
  - tool router（NL 路由/skill 优先）
  - report generator（pipeline_report 元信息）
  - memory manager（任务快照与复盘提示）

### 2.3 任务记忆层

组件：`src/geoclaw_qgis/memory/`

- 短期 memory：记录每次任务输入参数、状态、错误
- 长期 memory：自动复盘结果
- 归档机制：短期任务按时间迁移到 archive
- 检索机制：基于哈希向量的相似度检索

### 2.4 分析执行层

- Pipeline 执行：`scripts/run_qgis_pipeline.py`
- 单算法执行：`scripts/geoclaw_operator_runner.py`
- 原生案例执行：`scripts/geoclaw_case_runner.py`
- 轨迹网络执行：`src/geoclaw_qgis/analysis/network_ops.py`

### 2.5 AI 扩展层

组件：`src/geoclaw_qgis/ai/`

- 多 provider：OpenAI / Qwen / Gemini
- 协议：OpenAI-compatible chat completions
- 自动上下文压缩：长输入自动摘要保留关键信息

### 2.6 安全控制层

组件：`src/geoclaw_qgis/security/output_guard.py`

策略：

- 强制输出路径位于 `data/outputs`
- 禁止输入输出同路径（防止覆盖/删除输入）

## 3. 典型流程

1. 会话启动时加载 `soul.md/user.md` 并构建结构化 profile 对象。
2. 用户通过 CLI 或 `nl` 发起任务。
3. planner/tool-router 结合 profile 决策执行计划。
4. CLI 记录短期 memory（start_task）。
5. 业务模块执行（run/operator/network/skill/update）。
6. report generator 写入 profile 元信息。
7. CLI 写入任务结束状态并自动复盘到长期 memory。
8. 结果输出在 `data/outputs` 或 memory 目录。

## 4. 扩展策略

- 新案例：新增 pipeline + 可选 skill 注册
- 新 AI provider：扩展 `ExternalAIConfig.from_env`
- 新安全策略：扩展 `validate_output_targets`
- 新 NL 意图：扩展 `src/geoclaw_qgis/nl/intent.py`
- 新 profile 字段：扩展 `src/geoclaw_qgis/profile/layers.py`

## 5. 工程约束

- 输出目录约束优先于灵活性
- memory 不影响主流程（memory 异常只告警，不阻塞业务命令）
- 网络相关能力（TrackIntel）采用可选依赖机制

## 6. TODO（架构）

- TODO: 增加 provider 级限流与重试策略。
- TODO: 将 memory 检索升级为可插拔向量后端。
- TODO: 引入 pipeline schema 静态校验（参数类型、引用检查）。
