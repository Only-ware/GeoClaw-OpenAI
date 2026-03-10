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
OUT_ROOT="data/outputs/dialogue_suite_${TS}"
RAW_DIR="$OUT_ROOT/raw"
REPORT="$OUT_ROOT/dialogue_report.md"
SESSION="dialogue_suite_${TS}"
TMP_HOME="/tmp/geoclaw_dialogue_suite_${TS}"

mkdir -p "$RAW_DIR" "$TMP_HOME"

export GEOCLAW_OPENAI_HOME="$TMP_HOME"
export GEOCLAW_AI_PROVIDER="${GEOCLAW_AI_PROVIDER:-openai}"
export GEOCLAW_AI_BASE_URL="${GEOCLAW_AI_BASE_URL:-https://api.openai.com/v1}"
export GEOCLAW_AI_MODEL="${GEOCLAW_AI_MODEL:-gpt-5-mini}"

PASS=0
FAIL=0

append_report_header() {
  cat > "$REPORT" <<MD
# GeoClaw 15-Round Dialogue Regression Report

- generated_at: $(date -Iseconds)
- workspace: $ROOT
- output_root: $OUT_ROOT
- session_id: $SESSION
- ai_provider: $GEOCLAW_AI_PROVIDER
- ai_model: $GEOCLAW_AI_MODEL
- isolated_home: $TMP_HOME

## Scope

This run covers:
- casual chat
- user.md hot-update via chat
- tool execution from chat (\`--execute\`)
- NL planning and SRE external reasoning
- skill pipeline + AI summary
- builtin skills (operator/network)
- local command trigger and memory status

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

  {
    echo "## ${id} ${title}"
    echo
    echo "- user_prompt: ${user_msg}"
    echo "- command: \
\`\`\`bash
$cmd
\`\`\`"
    echo "- status: ${status}"
    echo "- raw_log: ${out}"
    echo
    echo "\`\`\`json"
    sed -n '1,120p' "$out"
    echo "\`\`\`"
    echo
  } >> "$REPORT"
}

append_report_header

run_round "R01" "Casual Chat CN" \
  "你好，先闲聊一下，你今天怎么样？" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --new-session --message '你好，先闲聊一下，你今天怎么样？' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R02" "Self Introduction EN (Regression)" \
  "Hi GeoClaw, can you briefly introduce yourself?" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'Hi GeoClaw, can you briefly introduce yourself?' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R03" "Summarize Previous Turn (Regression)" \
  "Can you summarize what I asked in previous turn?" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'Can you summarize what I asked in previous turn?' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R04" "Update user.md via Chat" \
  "请根据这次对话更新user.md：偏好英文、回答简洁。" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message '请根据这次对话更新user.md：偏好英文、回答简洁。' --with-ai" \
  '"intent": "profile"' '"profile_update"'

run_round "R05" "Profile Effect Check" \
  "Please answer in English with one short sentence: profile updated." \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'Please answer in English with one short sentence: profile updated.' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R06" "Chat Trigger Tool Execute" \
  "check for updates" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'check for updates' --with-ai --execute" \
  '"intent": "update"' '"execution"'

run_round "R07" "NL Preview Site Selection" \
  "Top 5 mall locations in Wuhan" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl 'Top 5 mall locations in Wuhan'" \
  '"intent": "run"' '"command_preview"'

run_round "R08" "NL + SRE External + Execute (Composite)" \
  "请基于data-dir data/raw/wuhan_osm分析武汉最适合建商场的前5个地点" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '请基于data-dir data/raw/wuhan_osm分析武汉最适合建商场的前5个地点' --use-sre --sre-reasoner-mode external --execute" \
  '"sre_enabled": true' '"execute": true'

run_round "R09" "Skill Registry Listing" \
  "列出可用 skills" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --list" \
  'mall_site_selection_qgis' 'network_trackintel_skill'

run_round "R10" "Skill Pipeline + AI Summary" \
  "运行 mall_site_selection_qgis skill 并输出 AI 总结" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill mall_site_selection_qgis --skip-download --set location_input=$OUT_ROOT/../wuhan_location/grid_location.gpkg --set out_dir=$OUT_ROOT/mall_skill --set top_n=5 --with-ai --ai-input 'Please summarize top mall candidates and key risks.'" \
  '"skill": "mall_site_selection_qgis"' '"report_source"'

run_round "R11" "AI Skill" \
  "运行 mall_site_selection_llm skill" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill mall_site_selection_llm --ai-input 'City: Wuhan. Goal: top 5 mall locations with explainable scoring.'" \
  '"skill": "mall_site_selection_llm"' '"ai_response"'

run_round "R12" "Builtin Skill: QGIS Operator" \
  "通过 qgis_operator_skill 计算候选地块质心" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill qgis_operator_skill --args '--algorithm native:centroids --param INPUT=$OUT_ROOT/mall_skill/mall_top_cells.gpkg --param-json ALL_PARTS=0 --param OUTPUT=$OUT_ROOT/operator/mall_top_centroids.gpkg'" \
  '"skill": "qgis_operator_skill"' '"executed_command"'

run_round "R13" "Builtin Skill: TrackIntel Network Dry-run" \
  "通过 network_trackintel_skill 做 dry-run" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill network_trackintel_skill --args '--pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv --out-dir $OUT_ROOT/network --dry-run'" \
  '"skill": "network_trackintel_skill"' '"executed_command"'

run_round "R14" "NL Local Tool Execute" \
  "执行命令: ls data/examples/trajectory" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '执行命令: ls data/examples/trajectory' --execute" \
  '"intent": "local"' '"execute": true'

run_round "R15" "NL Memory Status Execute" \
  "查看memory状态" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '查看memory状态' --execute" \
  '"intent": "memory"' '"execute": true'

{
  echo "## Summary"
  echo
  echo "- total_rounds: 15"
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

echo "REPORT=$REPORT"
echo "PASS=$PASS FAIL=$FAIL"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
