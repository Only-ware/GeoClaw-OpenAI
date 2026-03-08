# GeoClaw Soul/User 分层说明（v3.0.0）

## 1. 设计目标

GeoClaw v3.0.0 引入双层长期配置：

- `soul.md`：系统级身份、推理原则、执行边界（高优先级）
- `user.md`：用户长期画像与偏好（软个性化）

两者在会话初始化时自动加载、解析为结构化对象，统一供以下模块消费：

- planner（NL 计划）
- tool router（命令路由）
- report generator（`pipeline_report.json`）
- memory manager（短期快照与长期复盘）

## 2. 文件位置与优先级

默认路径：

- `~/.geoclaw-openai/soul.md`
- `~/.geoclaw-openai/user.md`

可选覆盖：

- `GEOCLAW_SOUL_PATH`
- `GEOCLAW_USER_PATH`

初始化命令：

```bash
geoclaw-openai profile init
```

查看当前加载：

```bash
geoclaw-openai profile show
```

## 3. 解析输出（结构化）

核心对象：`SessionProfile`

- `SessionProfile.soul`：`SoulConfig`
- `SessionProfile.user`：`UserProfile`

关键上下文方法：

- `planner_context()`
- `tool_router_context()`
- `report_context()`
- `memory_context()`

实现文件：`src/geoclaw_qgis/profile/layers.py`

## 4. 模块接入说明

1. planner（`src/geoclaw_qgis/nl/intent.py`）
- `parse_nl_query(query, session=...)` 接收 profile 上下文。
- 原因链中记录 profile 驱动的规划说明。

2. tool router（`src/geoclaw_qgis/cli/main.py` 与 `scripts/geoclaw_skill_runner.py`）
- `nl --execute` 前根据 profile 对场景进行路由策略调整（如商场选址优先注册 skill）。
- skill runner 输出包含 `tool_router_context` 与 profile 路径元信息。

3. report generator（`scripts/run_qgis_pipeline.py`）
- 在 `pipeline_report.json` 写入 `agent_layers`，包含 mission、执行层级、报告要求。

4. memory manager（`src/geoclaw_qgis/memory/store.py`）
- 每个短期任务写入 `profile_snapshot`。
- 自动复盘时引用长期偏好（如复现要求、约束习惯）。

## 5. 约束原则

- `soul.md` 优先级高于 `user.md`。
- `user.md` 不能覆盖安全边界与系统执行约束。
- 该层用于长期配置，不用于临时任务状态记录。
