# Chat Mode Case: Jingdezhen Mall Top5

Query:
- 请你下载景德镇的数据，并分析最适合建设商场的前5个地址，输出报告

Run command:
```bash
python3 -m geoclaw_qgis.cli.main chat --message "请你下载景德镇的数据，并分析最适合建设商场的前5个地址，输出报告" --no-ai --execute --use-sre --sre-report-out data/outputs/reasoning/chat_jingdezhen_mall_top5_report.md
```

Generated artifacts:
- `chat_process.json`
- `chat_run_output.json` (raw full output)
- `jingdezhen_mall_top5_report.md`
- `jingdezhen_site_top5_summary.csv`

Execution summary:
- `execution_result.return_code = 0`
- `tool_route_notes` confirms explicit city preservation:
  - `Detected explicit non-Wuhan input source; keep native run route...`
  - `Kept explicit NL-prioritized route; rejected conflicting SRE reroute.`
- Top5 scores (`jingdezhen_site_top5_summary.csv`):
  - `1,55.0,PRIORITY_A`
  - `2,54.1398,PRIORITY_A`
  - `3,53.9491,PRIORITY_A`
  - `4,53.3059,PRIORITY_A`
  - `5,53.0679,PRIORITY_A`

Notes:
- This case validates `chat --execute` delegates actionable requests to NL workflow execution.
- Non-Wuhan explicit city input is preserved (`景德镇市`) and route stays on native `run` flow.
