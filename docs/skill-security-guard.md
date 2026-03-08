# GeoClaw Skill 安全门禁说明（v3.1.0）

GeoClaw 提供注册前安全评估流程，防止恶意或高危 skill 注入：

1. `skill-registry assess`：评估风险，不写入系统。
2. `skill-registry register`：基于评估结果注册，必须用户确认。

## 1. 命令入口

```bash
# 评估
geoclaw-openai skill-registry assess --spec-file configs/examples/new_skill.json

# 注册（低/中风险）
geoclaw-openai skill-registry register --spec-file configs/examples/new_skill.json --confirm
```

## 2. 风险等级

- `low`：可直接注册（仍需确认）。
- `medium`：建议人工复核后注册。
- `high`：默认阻断。

如确需注册高风险 skill（不推荐）：

```bash
geoclaw-openai skill-registry register \
  --spec-file configs/examples/high_risk_skill_injection.json \
  --allow-high-risk \
  --confirm
```

## 3. 评估规则示例

- 路径安全：禁止绝对路径、`..` 路径穿越、越界路径。
- pipeline 约束：需在 `pipelines/` 下且文件存在。
- report_path 约束：建议位于 `data/outputs/` 下。
- 文本检测：检测危险命令、提示词注入、敏感凭据关键词。

## 4. 审计日志

评估与注册行为写入：

- `~/.geoclaw-openai/security/skill_guard_log.jsonl`

建议团队在 CI 或审计脚本中定期扫描该日志。

## 5. 高危模拟样例

示例文件：

- `configs/examples/high_risk_skill_injection.json`

快速验证高危阻断：

```bash
geoclaw-openai skill-registry assess \
  --spec-file configs/examples/high_risk_skill_injection.json

geoclaw-openai skill-registry register \
  --spec-file configs/examples/high_risk_skill_injection.json \
  --confirm
```

第二条命令应被阻断（risk_level=high）。
