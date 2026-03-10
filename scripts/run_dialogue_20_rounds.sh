#!/usr/bin/env bash
set -u

ROOT="/Volumes/Yaoy/project/AI-Agents"
cd "$ROOT"
PY_BIN="$(command -v python3)"

if [[ -z "${GEOCLAW_AI_API_KEY:-}" ]]; then
  echo "ERROR: GEOCLAW_AI_API_KEY is required in environment."
  exit 2
fi

TS="$(date +%Y%m%d_%H%M%S)"
OUT_ROOT="data/outputs/dialogue_suite20_${TS}"
RAW_DIR="$OUT_ROOT/raw"
REPORT="$OUT_ROOT/dialogue_report.md"
EASY_REPORT="$OUT_ROOT/dialogue_report_easy.md"
SESSION="dialogue_suite20_${TS}"
TMP_HOME="/tmp/geoclaw_dialogue_suite20_${TS}"
META="$OUT_ROOT/rounds_meta.tsv"

mkdir -p "$RAW_DIR" "$TMP_HOME"

export GEOCLAW_OPENAI_HOME="$TMP_HOME"
export GEOCLAW_AI_PROVIDER="${GEOCLAW_AI_PROVIDER:-openai}"
export GEOCLAW_AI_BASE_URL="${GEOCLAW_AI_BASE_URL:-https://api.openai.com/v1}"
export GEOCLAW_AI_MODEL="${GEOCLAW_AI_MODEL:-gpt-5-chat-latest}"

PASS=0
FAIL=0

echo -e "id\ttitle\tuser_prompt\tcommand\tstatus\traw_log" > "$META"

append_report_header() {
  cat > "$REPORT" <<MD
# GeoClaw 20-Round Dialogue Regression Report

- generated_at: $(date -Iseconds)
- workspace: $ROOT
- output_root: $OUT_ROOT
- session_id: $SESSION
- ai_provider: $GEOCLAW_AI_PROVIDER
- ai_model: $GEOCLAW_AI_MODEL
- isolated_home: $TMP_HOME

## Coverage

- chat/casual conversation and robust routing
- user.md hot update and effect verification
- chat-triggered tool execution
- nl local/memory/run/sre composite routes
- reasoning external LLM route
- skill registry / ai skill / pipeline skill / builtin skills
- operator + network combined scenarios

MD
}

run_round() {
  local id="$1"
  local title="$2"
  local user_msg="$3"
  local cmd="$4"
  local expect_a="${5:-}"
  local expect_b="${6:-}"

  local out="$RAW_DIR/${id}.log"
  local status="PASS"
  local rc=0

  echo "[$id] $title"
  eval "$cmd" >"$out" 2>&1 || rc=$?
  if [[ $rc -ne 0 ]]; then
    status="FAIL(rc=$rc)"
  fi

  if [[ -n "$expect_a" ]] && ! rg -q -- "$expect_a" "$out"; then
    status="${status};EXPECT_MISS(${expect_a})"
  fi
  if [[ -n "$expect_b" ]] && ! rg -q -- "$expect_b" "$out"; then
    status="${status};EXPECT_MISS(${expect_b})"
  fi

  if [[ "$status" == PASS ]]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi

  printf "%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$id" "$title" "$user_msg" "$cmd" "$status" "$out" >> "$META"

  {
    echo "## ${id} ${title}"
    echo
    echo "- user_prompt: ${user_msg}"
    echo "- command:"
    echo "\`\`\`bash"
    echo "$cmd"
    echo "\`\`\`"
    echo "- status: ${status}"
    echo "- raw_log: ${out}"
    echo
    echo "\`\`\`json"
    sed -n '1,140p' "$out"
    echo "\`\`\`"
    echo
  } >> "$REPORT"
}

append_report_header

run_round "R01" "Chat: define GeoClaw identity" \
  "请记住GeoClaw-OpenAI是GIS/GeoAI空间分析智能体，不是Clawpack海啸GeoClaw，并一句话介绍你自己。" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --new-session --message '请记住GeoClaw-OpenAI是GIS/GeoAI空间分析智能体，不是Clawpack海啸GeoClaw，并一句话介绍你自己。' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R02" "Chat regression: summarize previous turn" \
  "Can you summarize what I asked in previous turn?" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'Can you summarize what I asked in previous turn?' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R03" "Casual chat support" \
  "我今天有点累，先随便聊两句。" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message '我今天有点累，先随便聊两句。' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R04" "Profile update user.md" \
  "请根据本次对话更新user.md：偏好英文、回答简洁、工具偏好QGIS和OpenAI。" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message '请根据本次对话更新user.md：偏好英文、回答简洁、工具偏好QGIS和OpenAI。' --with-ai" \
  '"intent": "profile"' '"profile_update"'

run_round "R05" "Profile effect verification" \
  "Please reply in one concise English sentence: profile applied." \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'Please reply in one concise English sentence: profile applied.' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R06" "Chat execute update check" \
  "check for updates" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'check for updates' --with-ai --execute" \
  '"intent": "update"' '"execution"'

run_round "R07" "Chat unsolved request with alternatives" \
  "你能直接替我打开本机浏览器并登录网站吗？" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message '你能直接替我打开本机浏览器并登录网站吗？' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R08" "NL local tool execution" \
  "执行命令: ls data/examples/trajectory" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '执行命令: ls data/examples/trajectory' --execute" \
  '"intent": "local"' '"execute": true'

run_round "R09" "NL memory status execution" \
  "查看memory状态" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '查看memory状态' --execute" \
  '"intent": "memory"' '"execute": true'

run_round "R10" "NL run preview by city" \
  "Top 5 mall locations in Wuhan" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl 'Top 5 mall locations in Wuhan'" \
  '"intent": "run"' '"command_preview"'

run_round "R11" "NL run execute by data-dir" \
  "请基于data-dir data/raw/wuhan_osm分析武汉最适合建商场的前5个地点" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '请基于data-dir data/raw/wuhan_osm分析武汉最适合建商场的前5个地点' --execute" \
  '"intent": "run"' '"execute": true'

run_round "R12" "NL composite: SRE external + execute" \
  "请基于data-dir data/raw/wuhan_osm分析武汉最适合建商场的前3个地点并说明依据" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '请基于data-dir data/raw/wuhan_osm分析武汉最适合建商场的前3个地点并说明依据' --use-sre --sre-reasoner-mode external --execute" \
  '"sre_enabled": true' '"execute": true'

run_round "R13" "Reasoning external" \
  "为武汉商场选址设计可复现工作流" \
  "$PY_BIN -m geoclaw_qgis.cli.main reasoning '为武汉商场选址设计可复现工作流' --reasoner-mode external --llm-retries 1" \
  '"llm_model": "openai:gpt-5-chat-latest"' '"execution_plan"'

run_round "R14" "Skill list" \
  "列出可用skills" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --list" \
  'mall_site_selection_qgis' 'network_trackintel_skill'

run_round "R15" "AI skill: mall strategy" \
  "运行mall_site_selection_llm" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill mall_site_selection_llm --ai-input 'City: Wuhan; Goal: top 5 mall locations with explainable scoring and risks.'" \
  '"skill": "mall_site_selection_llm"' '"ai_response"'

run_round "R16" "Pipeline skill: vector basics" \
  "运行vector_basics_qgis" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill vector_basics_qgis --set raw_dir=data/raw/wuhan_osm --set out_dir=$OUT_ROOT/vector_skill --set buffer_m=900" \
  '"skill": "vector_basics_qgis"' '"report"'

run_round "R17" "Pipeline skill: raster basics" \
  "运行raster_basics_qgis" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill raster_basics_qgis --set raw_dir=data/raw/wuhan_osm --set out_dir=$OUT_ROOT/raster_skill --set grid_spacing_m=1800" \
  '"skill": "raster_basics_qgis"' '"report"'

run_round "R18" "Pipeline skill + AI summary: mall qgis" \
  "运行mall_site_selection_qgis并AI总结" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill mall_site_selection_qgis --skip-download --set location_input=data/outputs/wuhan_location/grid_location.gpkg --set out_dir=$OUT_ROOT/mall_skill --set top_n=6 --with-ai --ai-input 'Summarize top candidates, risks, and field-validation priorities.'" \
  '"skill": "mall_site_selection_qgis"' '"report_source"'

run_round "R19" "Builtin skill: operator on mall output" \
  "通过operator skill计算质心" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill qgis_operator_skill --args '--algorithm native:centroids --param INPUT=$OUT_ROOT/mall_skill/mall_top_cells.gpkg --param-json ALL_PARTS=0 --param OUTPUT=$OUT_ROOT/operator/mall_top_centroids.gpkg'" \
  '"skill": "qgis_operator_skill"' '"executed_command"'

run_round "R20" "Builtin skill: network dry-run" \
  "运行network trackintel dry-run" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill network_trackintel_skill --args '--pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv --out-dir $OUT_ROOT/network --dry-run'" \
  '"skill": "network_trackintel_skill"' '"executed_command"'

{
  echo "## Summary"
  echo
  echo "- total_rounds: 20"
  echo "- pass: $PASS"
  echo "- fail: $FAIL"
  echo "- generated_at: $(date -Iseconds)"
  echo "- raw_dir: $RAW_DIR"
  echo
  if [[ $FAIL -gt 0 ]]; then
    echo "Result: FAILED"
  else
    echo "Result: PASSED"
  fi
} >> "$REPORT"

# Generate easy-read report
"$PY_BIN" - "$META" "$EASY_REPORT" "$OUT_ROOT" <<'PY'
import json
import pathlib
import re
import sys
from typing import Any

meta_path = pathlib.Path(sys.argv[1])
out_path = pathlib.Path(sys.argv[2])
out_root = sys.argv[3]


def extract_json_objects(text: str) -> list[dict[str, Any]]:
    dec = json.JSONDecoder()
    objs: list[dict[str, Any]] = []
    i = 0
    n = len(text)
    while i < n:
        j = text.find("{", i)
        if j < 0:
            break
        try:
            obj, end = dec.raw_decode(text[j:])
        except Exception:
            i = j + 1
            continue
        if isinstance(obj, dict):
            objs.append(obj)
        i = j + end
    return objs


def pick_primary(objs: list[dict[str, Any]]) -> dict[str, Any]:
    if not objs:
        return {}
    priorities = [
        lambda o: "chat" in o,
        lambda o: "execution" in o and "intent" in o,
        lambda o: "intent" in o and "query" in o,
        lambda o: "skill" in o,
        lambda o: "success" in o and "engine" in o,
    ]
    for cond in priorities:
        for o in objs:
            if cond(o):
                return o
    return objs[0]


def short_text(s: str, limit: int = 160) -> str:
    t = " ".join(str(s or "").split())
    return t if len(t) <= limit else t[: limit - 1] + "…"


def collect_paths(text: str) -> list[str]:
    pats = [
        r"/[^\s\"']+",
        r"data/outputs/[^\s\"']+",
    ]
    vals: list[str] = []
    for p in pats:
        vals.extend(re.findall(p, text))
    clean: list[str] = []
    for v in vals:
        vv = v.rstrip(",.;)]")
        if any(vv.endswith(ext) for ext in [".gpkg", ".json", ".csv", ".tif", ".md", ".png"]) or "data/outputs/" in vv:
            clean.append(vv)
    out: list[str] = []
    seen = set()
    for c in clean:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:6]


rows = meta_path.read_text(encoding="utf-8").splitlines()
header = rows[0].split("\t")
records = [dict(zip(header, line.split("\t"))) for line in rows[1:] if line.strip()]

lines: list[str] = []
lines.append("# GeoClaw 20轮对话易读报告（Q/A/过程/输出）")
lines.append("")
lines.append(f"- 输出目录: `{out_root}`")
import datetime as dt
generated_at = dt.datetime.fromtimestamp(pathlib.Path(meta_path).stat().st_mtime).isoformat()
lines.append(f"- 生成时间: {generated_at}")
lines.append("")

for rec in records:
    rid = rec["id"]
    title = rec["title"]
    q = rec["user_prompt"]
    cmd = rec["command"]
    status = rec["status"]
    raw_log = rec["raw_log"]
    text = pathlib.Path(raw_log).read_text(encoding="utf-8", errors="ignore")
    objs = extract_json_objects(text)
    obj = pick_primary(objs)

    a = ""
    if "chat" in obj and isinstance(obj.get("chat"), dict):
        a = short_text(obj["chat"].get("reply", ""))
    elif "execution" in obj and isinstance(obj.get("execution"), dict):
        ex = obj["execution"]
        rc = ex.get("return_code", "")
        a = f"执行完成，return_code={rc}"
    elif "skill" in obj:
        a = f"skill={obj.get('skill')} 执行完成"
        if isinstance(obj.get("ai"), dict) and obj["ai"].get("summary"):
            a += "，并生成AI总结"
    elif "success" in obj:
        a = f"network dry-run success={obj.get('success')}"
    else:
        a = short_text(text)

    process = ""
    if " chat " in f" {cmd} ":
        process = "Chat 模式（可结合会话历史与用户偏好）"
    elif " nl " in f" {cmd} ":
        process = "自然语言路由（NL），自动识别 intent 并执行"
    elif " reasoning " in f" {cmd} ":
        process = "SRE 推理引擎（外部LLM模式）"
    elif " skill " in f" {cmd} ":
        process = "Skill 执行链路（注册技能/内置技能）"
    else:
        process = "命令执行"

    paths = collect_paths(text)

    lines.append(f"## {rid} {title}")
    lines.append(f"- Q: {q}")
    lines.append(f"- A(摘要): {a if a else '见原始日志'}")
    lines.append(f"- 过程: {process}")
    lines.append(f"- 结果状态: {status}")
    lines.append(f"- 原始日志: `{raw_log}`")
    if paths:
        lines.append("- 输出路径:")
        for p in paths:
            lines.append(f"  - `{p}`")
    else:
        lines.append("- 输出路径: 无结构化文件输出（见日志）")
    lines.append("")

lines.append("## 总结")
pass_count = sum(1 for r in records if r.get("status") == "PASS")
fail_count = len(records) - pass_count
lines.append(f"- 总轮次: {len(records)}")
lines.append(f"- 通过: {pass_count}")
lines.append(f"- 失败: {fail_count}")
lines.append("- 说明: 若失败轮次>0，请在对应 raw 日志中查看失败原因并回归修复。")

out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

echo "REPORT=$REPORT"
echo "EASY_REPORT=$EASY_REPORT"
echo "PASS=$PASS FAIL=$FAIL"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
