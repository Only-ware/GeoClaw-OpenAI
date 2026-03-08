# GeoClaw 3.0 SRE 重构实施方案（内部草案）

版本：v3.0.0 内部开发阶段  
状态：Phase 3-4（Milestone A-F 已落地，Release Candidate Ready）

## 1. 目标

在不破坏现有稳定执行链路（run/operator/network/skill）的前提下，引入 Spatial Reasoning Engine（SRE）中枢，形成：

- 输入标准化
- 规则约束
- 可解释方法选择
- 一致性校验
- 结构化 workflow 输出

## 2. 当前落地范围（本步）

新增模块：`src/geoclaw_qgis/reasoning/`

- `schemas.py`：`ReasoningInput` 与 `SpatialReasoningResult` 核心 schema
- `input_adapter.py`：输入统一构造（含 profile 映射）
- `context_builder.py`：预处理上下文
- `task_typer.py`：任务候选识别
- `primitive_resolver.py`：地理原语解析
- `template_library.py`：方法模板映射
- `rule_engine.py`：硬规则（CRS/策略）
- `llm_reasoner.py`：Phase 1 的确定性占位推理器
- `validator.py`：约束/一致性基础校验
- `workflow_synthesizer.py`：汇总为 `SpatialReasoningResult`
- `engine.py`：端到端编排入口

说明：当前为“可测试骨架”，已接入 CLI 灰度路径（`nl --use-sre`），默认路径仍保留 legacy fallback。

补充（Phase 1-1 ~ 1-2）：

- 新增 CLI 内部命令：`geoclaw-openai reasoning ...`
- 新增 NL 灰度开关：`geoclaw-openai nl --use-sre [--sre-strict]`
- 新增数据目录适配器：自动发现 `geojson/gpkg/shp/tif/csv` 元信息（过滤隐藏文件）
- 新增 `execution_plan`：由 SRE 输出建议执行命令（含安全阻断标记）
- `cmd_nl` 优先消费 `execution_plan`，并在 strict + fail 时阻断执行
- 覆盖测试：execution route safe/block 两类路径

## 3. 分阶段推进

### Phase 1（底线）

- 输入标准化
- CRS/extent/geometry/safety 规则
- 基础 validator
- 输出 schema

验收：不犯低级 GIS 错误，可稳定输出结构化结果。

### Phase 2（模板）

- proximity/accessibility/site-selection/change/trajectory 模板完善
- workflow steps 参数化
- 接入 Data Catalog 元数据质量判定

验收：常见任务有标准化推理链。

### Phase 3（高级推理）

- MAUP/尺度效应
- exploratory vs causal 区分
- uncertainty 与 sensitivity 提示
- LLM 高级方法权衡

验收：具备高质量方法解释与风险提示。

## 4. 集成策略

- 先以旁路模式引入：新增 `run_spatial_reasoning(...)` 供内部调用。
- CLI 仅在灰度参数开启时走 SRE（后续步骤实现）。
- 保留原有规划链作为 fallback，直到 SRE 稳定。

## 5. 测试门禁

每一步必须通过：

1. 新增模块单测（结构、规则、校验、输出）
2. 现有单测全量回归
3. 日常链路回归（必要时 day_run）

本步测试结果（2026-03-08 本地，滚动更新）：

- SRE/CLI 定向测试：`40/40` 通过
- 全量单测：`73/73` 通过
- CLI 冒烟：
  - `nl "商场选址分析" --use-sre` -> 命令路由到 `mall_site_selection_qgis`
  - `reasoning "...变化检测..." --strict` -> 校验失败时 exit code=1
- day-run 回归：
  - `bash scripts/day_run.sh` -> success
  - 覆盖 `run + skill + reasoning + nl(use-sre) + memory` 全链路

## 6. 后续步骤与时间评估（单人开发，内部迭代）

前提假设：

- 以本地开发为主，不做线上部署与云资源编排。
- 每阶段均需通过全量单测与至少 2 条 CLI 冒烟链路。
- 工期为净开发时间，不含外部数据准备等待。

### Milestone A：规则/模板配置化（Phase 2-1）

- 目标：
  - 将当前硬编码规则迁移到 `reasoning/rules/*.yaml`
  - 将方法模板迁移到 `reasoning/templates/*.yaml`
  - 引入配置加载器与 schema 校验
- 实际：`1` 人天（首版）
- 验收：
  - 规则与模板热加载（含回退默认配置）
  - 新增配置加载单测
  - ✅ 已完成（本地）
    - 新增 `reasoning/rules/*.yaml` 与 `reasoning/templates/*.yaml`
    - 新增 `config_loader.py`（支持 strict 校验与缓存清理）
    - `rule_engine/template_library` 已切换到配置读取
    - 新增 `test_reasoning_config_loader.py`

### Milestone B：Workflow 参数化增强（Phase 2-2）

- 目标：
  - `workflow_plan.steps.parameters` 根据 query/datasets 生成可执行参数
  - 输出 `required_preconditions` 与 `revisions_applied`（用于执行前修正记录）
- 预计：`3-4` 人天
- 验收：
  - proximity/site_selection/change/trajectory 各至少 1 条参数化用例
  - strict 模式下阻断与修正逻辑可追踪
  - ⏳ 进行中（已完成首批能力）
    - `validation` 新增 `required_preconditions` / `revisions_applied`
    - `workflow_plan.steps.parameters` 已支持距离半径与选址权重等基础参数生成
    - `workflow_plan.preconditions` 已支持 `unify_crs` / `validate_extent_overlap` 结构化输出
    - `nl --use-sre` 的 `tool_route_notes` 已追加 preconditions/revisions 摘要，便于路由审计
    - 单测覆盖已包含 proximity/site_selection/change/trajectory 参数化断言

### Milestone C：Router 深度集成（Phase 2-3）

- 目标：
  - 将 `execution_plan` 完整接入 run/operator/network/skill 四类路由策略
  - 增加 route explainability（为何选该命令、为何 fallback）
- 预计：`2` 人天
- 验收：
  - `nl --use-sre` 在 4 类任务下 route 行为稳定
  - fallback 场景日志完整
  - ⏳ 进行中（已完成首批安全接入）
    - `cmd_nl` 已优先应用 `execution_plan`，并回退到 legacy route
    - `tool_route_notes` 已显示 preconditions/revisions/blocked reasons
    - SRE 下发命令新增白名单根命令校验（拒绝未知高风险路由）
    - SRE 下发命令新增形状校验（`run/operator/network/skill` 关键参数检查）
    - 新增意图兼容策略，阻断跨意图重路由（如 `operator -> run`）
    - 非空间意图（memory/update）在 `--use-sre` 下自动跳过 SRE 并记录说明
    - 新增 `cmd_nl` 级 mock 集成测试（跨意图阻断、同意图应用、非空间跳过）

### Milestone D：高级地理推理（Phase 3-1）

- 目标：
  - MAUP/尺度效应提示
  - exploratory vs causal 区分
  - 参数敏感性与不确定性评分增强
- 预计：`3-4` 人天
- 验收：
  - validator 新增对应规则与告警码
  - 报告层可消费结构化 caveat 字段
  - ⏳ 进行中（核心能力已落地）
    - `reasoning_summary` 新增：
      - `reasoning_mode`（exploratory/causal_inference）
      - `uncertainty_score`
      - `sensitivity_hints`
      - `uncertainty_factors`
    - rule_engine 新增高级信号：
      - causal/exploratory 模式识别
      - 参数敏感性提示（buffer 半径、尺度、权重、时间窗）
      - 不确定性因子聚合
    - validator 新增高级校验：
      - `CAUSAL_GUARDRAIL_REQUIRED`
      - `MISSING_SENSITIVITY_HINTS`
      - `MISSING_UNCERTAINTY_SCORE`
      - `SCALE_EFFECTS_NOT_EXPLAINED`
    - 新增报告层消费能力：
      - `reasoning/report_generator.py` 可将高级 caveat 输出为 Markdown 报告
      - CLI 新增 `reasoning --report-out/--print-report`
      - 报告输出受输出目录安全策略约束（仅 `data/outputs`）
    - 已补专项测试：
      - 因果意图 guardrail + 高不确定性
      - MAUP 关键词触发尺度敏感与局限说明
      - reasoning 报告生成与输出安全测试

### Milestone E：LLM 推理器升级（Phase 3-2）

- 目标：
  - 将 `llm_reasoner` 从 deterministic 占位升级到可配置 provider
  - 强制结构化输出与校验重试
- 预计：`3-5` 人天
- 验收：
  - provider 切换可测
  - 结构化输出失败可自动降级
  - ⏳ 进行中（核心能力已落地）
    - `llm_reasoner` 已支持 `auto/deterministic/external` 三模式
    - 外部 LLM 响应支持：
      - JSON 结构提取与校验
      - 最多 N 次重试（可配置）
      - strict 模式失败即抛错
      - non-strict 自动降级 deterministic
    - reasoner 配置化能力：
      - 新增 `templates/llm_reasoner.yaml`
      - prompt 与 output schema 从配置加载（可按项目覆盖）
      - external payload 按 schema 做强校验后才进入合并流程
      - 非 strict 下若 `llm_reasoner.yaml` 配置损坏，将自动回退默认模板（strict 下保持抛错）
    - CLI 新增 reasoner 控制参数：
      - `reasoning --reasoner-mode/--llm-retries/--strict-external`
      - `nl --sre-reasoner-mode/--sre-llm-retries/--sre-strict-external`
    - 专项测试已补：
      - 外部模式成功
      - 重试后成功
      - schema 不合规后重试成功
      - `reasoning/assumptions/limitations` 非列表结构触发重试
      - 非严格降级
      - 严格模式失败
      - 外部错误细节脱敏（避免 API key 片段泄露）

### Milestone F：稳定性与文档收敛（Release Candidate）

- 目标：
  - day-run 回归（典型案例集）
  - 文档与教程统一（CLI / SRE / Skill / Memory）
- 预计：`2` 人天
- 验收：
  - 全量测试通过
  - 典型案例输出可复现
  - ✅ 已完成（本地）
    - `day_run.sh` 已扩展覆盖 `run/skill/reasoning/nl/memory` 回归矩阵
    - day-run 新增报告产物校验：
      - `data/outputs/reasoning/day_run_reasoning.md`
      - `data/outputs/reasoning/day_run_nl_e2e_report.md`
    - README / development-guide / technical-reference 已同步 day-run 与验证口径

整体预计：`15-20` 人天（约 3-4 周，按单人全职节奏）
