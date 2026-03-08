# Example: 武汉商场选址 Top-5（自然语言端到端）

本示例用于演示新手如何通过一句自然语言完成商场选址，并输出可复现结果。

## 1. 运行方式

在工程根目录执行：

```bash
bash data/examples/site_selection/wuhan_mall_top5/run_nl_wuhan_mall_top5.sh
```

或直接执行命令：

```bash
geoclaw-openai nl "武汉最适合建商场的前5个地点，输出结果和简要解释" \
  --use-sre \
  --sre-reasoner-mode deterministic \
  --sre-report-out data/outputs/reasoning/wuhan_mall_top5_report.md \
  --execute
```

## 2. 输出结果

- 候选点：`data/outputs/mall_site_qgis/mall_candidates.gpkg`
- 推理报告：`data/outputs/reasoning/wuhan_mall_top5_report.md`
- Skill 报告：`data/outputs/mall_site_qgis/pipeline_report.json`

## 3. 校验（可选）

```bash
ogrinfo -ro data/outputs/mall_site_qgis/mall_candidates.gpkg -sql "SELECT COUNT(*) AS cnt FROM mall_candidates"
```

期望 `cnt=5`。
