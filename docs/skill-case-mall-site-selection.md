# GeoClaw Skill 案例：商场选址分析（LLM 与 QGIS Processing 两种写法，v2.3.4）

本文给出同一个业务目标的两种 skill 实现方式：

- 写法 A：`mall_site_selection_llm`（大语言模型推理）
- 写法 B：`mall_site_selection_qgis`（QGIS Processing 流程）

目标：用 GeoClaw 指标体系支持“商场选址”。

## 1. 写法 A：LLM Skill（策略规划型）

### 1.1 Skill 定义（registry）

位置：`configs/skills_registry.json`

- `id`: `mall_site_selection_llm`
- `type`: `ai`
- `system_prompt`: 定义输出结构（目标约束、评分公式、候选区画像、风险与建议）

### 1.2 运行方式

```bash
# 直接输入问题（未配置 API 时会返回 warning，但命令不失败）
geoclaw-openai skill -- --skill mall_site_selection_llm --ai-input "基于武汉的人流与可达性，给出商场选址策略"

# 需要强制 AI 成功（无 key 则失败）
geoclaw-openai skill -- --skill mall_site_selection_llm --require-ai --ai-input "请输出前3类候选区条件"
```

### 1.3 适用场景

- 快速形成方案草案
- 方案解释和沟通
- 多约束策略推演（预算、竞品、交通、政策）

## 2. 写法 B：QGIS Processing Skill（可复现计算型）

### 2.1 Skill 定义（registry + pipeline）

位置：

- `configs/skills_registry.json` 中 `mall_site_selection_qgis`
- `pipelines/cases/mall_site_selection_qgis.yaml`

核心流程：

1. 可行区过滤（ACCESS/HEAT/SAFETY/SERVICE 阈值）
2. 计算 `MALL_SCORE`
3. 生成 `MALL_RANK`
4. 生成 `MALL_CLASS`
5. 提取 Top-N 并转候选点

关键输出：

- `data/outputs/mall_site_qgis/mall_candidates.gpkg`
- `data/outputs/mall_site_qgis/pipeline_report.json`

### 2.2 运行方式

```bash
# 先准备区位分析结果（若尚未生成）
geoclaw-openai run --case location_analysis --city "武汉市"

# 执行 QGIS skill
geoclaw-openai skill -- --skill mall_site_selection_qgis --skip-download
```

### 2.3 适用场景

- 需要可复现实验与定量对比
- 需要产出 GIS 图层供审阅和复核
- 需要稳定批处理

## 3. 对比建议

- 先用 LLM Skill 快速形成假设，再用 QGIS Skill 定量验证。
- 若面向科研论文或长期工程，优先保留 QGIS skill 输出与 `pipeline_report.json`。
- 若面向决策沟通，建议两者结合：QGIS 结果 + LLM 解释。

## 4. 测试建议

```bash
# 列出 skill，确认已注册
geoclaw-openai skill -- --list

# 测试 LLM 写法（无 key 也可检查流程）
geoclaw-openai skill -- --skill mall_site_selection_llm --ai-input "测试"

# 测试 QGIS 写法
geoclaw-openai skill -- --skill mall_site_selection_qgis --skip-download
```
