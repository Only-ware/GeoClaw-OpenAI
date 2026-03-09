# GeoClaw Skill 编写规范（项目 v3.1.2，规范 v1.0）

本文档定义 GeoClaw-OpenAI 项目中的 skill 编写要求，适用于 `configs/skills_registry.json` 中的 `pipeline`、`ai` 与 `builtin` 类型。

## 1. 总体原则

1. 可复现：同样输入应可得到同类输出结构。
2. 可审计：关键步骤要有输出文件或结构化文本。
3. 可扩展：参数和路径尽量模板化，避免硬编码机器私有路径。
4. 安全优先：输出必须落在 `data/outputs` 下，禁止覆盖输入文件。

## 2. Skill ID 规范

- 使用小写字母、数字、下划线：`[a-z0-9_]+`
- 建议格式：`<domain>_<task>_<impl>`
- 示例：
  - `mall_site_selection_qgis`
  - `mall_site_selection_llm`

## 3. Registry 字段规范

位置：`configs/skills_registry.json`

### 3.1 通用必填字段

- `id`：skill 唯一标识
- `type`：`pipeline`、`ai` 或 `builtin`
- `description`：一句话说明用途

### 3.2 pipeline 类型必填字段

- `pipeline`：YAML 路径（相对项目根目录）
- `report_path`：运行报告路径

### 3.3 pipeline 类型推荐字段

- `requires_osm`：是否依赖 OSM 下载
- `default_bbox`：默认研究范围
- `pre_steps`：前置 skill（仅已注册 skill id）

### 3.4 ai 类型必填字段

- `system_prompt`：稳定约束输出结构的提示词

### 3.5 builtin 类型必填字段

- `builtin`：GeoClaw 内置命令片段数组，如 `["operator"]`、`["network"]`、`["run"]`

### 3.6 builtin 类型推荐字段

- `default_args`：默认命令参数 token 列表，便于开箱即用
- `report_path`：若会产出报告，建议声明默认报告路径

## 4. Pipeline Skill 编写规范

### 4.1 文件位置

- 建议放在：`pipelines/cases/<skill_id>.yaml`

### 4.2 变量要求

- 必须提供 `out_dir` 变量，且默认值在 `data/outputs/` 下。
- 输入变量建议命名清晰，如 `location_input`、`raw_dir`。

### 4.3 输出要求

- 最终产物必须为可直接复核的文件（如 `.gpkg`、`.tif`）。
- 建议字段名使用大写业务语义，如 `MALL_SCORE`、`MALL_RANK`。

### 4.4 算法表达建议

- 阈值过滤：`native:extractbyexpression`
- 评分计算：`native:fieldcalculator`
- 排名：`native:addautoincrementalfield`
- 候选点提取：`native:centroids` + `native:retainfields`

## 5. LLM Skill 编写规范

### 5.1 system_prompt 要求

- 明确角色（如商业选址分析师）
- 明确输出结构（分点、字段、步骤）
- 明确限制（不要编造数据、说明假设）

### 5.2 输入建议

- 建议通过 `--ai-input` 提供任务上下文
- 若引用 pipeline 报告，建议先做上下文压缩（项目已内置自动压缩）

### 5.3 输出建议

- 结构化格式：结论、评分逻辑、风险、建议
- 说明数据不足项与后续采集建议

## 6. 测试规范（必须执行）

新增 skill 后，至少执行以下测试：

1. 注册加载测试
```bash
geoclaw-openai skill -- --list
```

0. 注册前安全评估（新增，必须）
```bash
geoclaw-openai skill-registry assess --spec-file <your_skill_spec.json>
```

2. pipeline skill 测试
```bash
geoclaw-openai skill -- --skill <pipeline_skill_id> --skip-download
```

3. ai skill 测试
```bash
geoclaw-openai skill -- --skill <ai_skill_id> --ai-input "smoke test"
```

4. builtin skill 测试
```bash
geoclaw-openai skill -- --skill <builtin_skill_id> --args "--help"
```

5. 单元测试
```bash
python3 -m unittest discover -s src/geoclaw_qgis/tests -p 'test_*.py'
```

## 8. 安全门禁流程（注册前评估 + 用户确认）

GeoClaw 已支持 `skill-registry` 安全门禁：

1. 先评估风险（不写入 registry）
```bash
geoclaw-openai skill-registry assess --spec-file configs/examples/new_skill.json
```

2. 再注册（必须确认）
```bash
geoclaw-openai skill-registry register \
  --spec-file configs/examples/new_skill.json \
  --confirm
```

规则：

- `risk_level=high` 默认阻断注册。
- 如确需写入高风险 skill，必须显式加 `--allow-high-risk` 且 `--confirm`。
- 安全日志写入：`~/.geoclaw-openai/security/skill_guard_log.jsonl`。

## 7. 评审清单（PR Checklist）

- [ ] skill id 命名符合规范
- [ ] registry JSON 结构合法
- [ ] pipeline 输出路径符合安全策略
- [ ] ai prompt 明确输出结构
- [ ] 文档已补充（案例 + 规范）
- [ ] 测试命令全部通过

## 9. 典型案例参考

- `docs/skill-case-mall-site-selection.md`
