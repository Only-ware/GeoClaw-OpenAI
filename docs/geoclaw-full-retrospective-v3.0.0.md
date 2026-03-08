# GeoClaw-OpenAI 全量复盘（截至 v3.0.0）

更新时间：2026-03-08（Asia/Shanghai）  
项目：GeoClaw-OpenAI  
机构：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 复盘目标

本文档总结项目从框架搭建到 v3.0.0 的核心演进、技术决策与当前边界，作为团队后续开发基线。

## 2. 版本里程碑

1. `v1.0.0`
- 形成区位分析、选址分析、综合案例与基础出图主链路。

2. `v1.1.0`
- 引入 memory（短期/长期）和 `update` 自更新能力。

3. `v2.0.0`
- 引入自然语言入口 `geoclaw-openai nl`。

4. `v2.1.0`
- 融合 TrackIntel 轨迹处理与 OD 网络分析。

5. `v3.0.0`
- 引入 `soul.md + user.md` 双层个性化架构并完成会话初始化加载。
- planner/tool-router/report/memory 四模块消费结构化 profile 对象。
- 新增 `profile init/show` 用户引导命令。
- SRE 3.0 重构里程碑 A-F 收口并新增 NL 端到端报告输出。

## 3. 当前能力版图

- 空间分析：区位、选址、综合案例
- 输入模式：city / bbox / data-dir（互斥）
- 制图能力：专题图 PNG + QGZ
- AI 扩展：Skill + 多 provider
- 个性化层：Soul（系统）+ User（用户）
- 智能交互：自然语言解析到 CLI
- 端到端报告：NL -> SRE -> Markdown 报告
- 记忆闭环：记录、复盘、归档、检索
- 轨迹分析：TrackIntel OD 网络
- 维护能力：自更新、day-run 回归

## 4. 关键工程决策

1. 统一 CLI 编排
- 将 run/operator/network/skill/memory/nl/update 纳入单一入口，降低维护成本。

2. 安全优先
- 输出路径固定到 `data/outputs`，防止实验阶段误覆盖原始输入。

3. 兼容优先的 AI 接入
- 使用 OpenAI-compatible 协议，同时支持 OpenAI/Qwen/Gemini。

4. 记忆默认开启
- 每次任务自动沉淀，减少重复试错。

5. 可选依赖策略
- TrackIntel 作为可选能力，不阻塞核心 GIS 主链路。
6. 分层个性化优先级
- `soul.md` 高优先级约束系统行为，`user.md` 提供软偏好，不覆盖安全边界。

## 5. 测试与稳定性

已形成的稳定性验证手段：

- 单元测试（AI provider、context、NL、memory、security）
- `scripts/day_run.sh` 主链路回归
- `scripts/run_trackintel_network_demo.sh` 轨迹模块 demo
- CLI 级 dry-run 与参数解析验证

## 6. 当前边界

1. memory 检索为轻量哈希向量方案，语义能力有限。
2. NL 解析仍以规则为主，复杂多约束请求存在提升空间。
3. 轨迹模块在大规模数据下的性能评估尚未系统化。

## 7. 下一阶段建议

1. 引入可插拔 embedding 后端，提升 memory 检索精度。
2. 增加 NL 多轮上下文与纠错机制。
3. 增加轨迹网络大样本基准测试与可视化模板。
4. 建立文档与 CLI 参数自动一致性检查。

## 8. 结论

GeoClaw-OpenAI 已完成从“原型验证”到“可复现科研工程系统”的转变。v3.0.0 的核心价值在于：

- 功能更完整（GIS + AI + Memory + NL + Mobility）
- 运行更安全（输出隔离）
- 扩展更灵活（多 provider + Skill + Profile Layers）

该版本可作为团队后续 3.x 迭代的稳定基线。
