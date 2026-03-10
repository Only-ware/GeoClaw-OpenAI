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
OUT_ROOT="data/outputs/dialogue_suite10_${TS}"
RAW_DIR="$OUT_ROOT/raw"
REPORT="$OUT_ROOT/dialogue_report.md"
SESSION="dialogue_suite10_${TS}"
TMP_HOME="/tmp/geoclaw_dialogue_suite10_${TS}"

mkdir -p "$RAW_DIR" "$TMP_HOME"

export GEOCLAW_OPENAI_HOME="$TMP_HOME"
export GEOCLAW_AI_PROVIDER="${GEOCLAW_AI_PROVIDER:-openai}"
export GEOCLAW_AI_BASE_URL="${GEOCLAW_AI_BASE_URL:-https://api.openai.com/v1}"
export GEOCLAW_AI_MODEL="${GEOCLAW_AI_MODEL:-gpt-5-chat-latest}"

PASS=0
FAIL=0

append_report_header() {
  cat > "$REPORT" <<MD
# GeoClaw 10-Round Dialogue Regression Report

- generated_at: $(date -Iseconds)
- workspace: $ROOT
- output_root: $OUT_ROOT
- session_id: $SESSION
- ai_provider: $GEOCLAW_AI_PROVIDER
- ai_model: $GEOCLAW_AI_MODEL
- isolated_home: $TMP_HOME

## Coverage

- casual chat
- user.md hot update via chat
- chat-triggered tool execution
- NL local tool execution
- NL + SRE external + execute (composite flow)
- skill listing
- pipeline skill + AI summary
- builtin network skill (TrackIntel dry-run)

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

run_round "R01" "Casual Chat + GeoClaw Definition" \
  "请记住GeoClaw-OpenAI是GIS/GeoAI空间分析智能体，不是Clawpack海啸GeoClaw，并一句话介绍你自己。" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --new-session --message '请记住GeoClaw-OpenAI是GIS/GeoAI空间分析智能体，不是Clawpack海啸GeoClaw，并一句话介绍你自己。' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R02" "Regression: summarize previous turn should stay chat" \
  "Can you summarize what I asked in previous turn?" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'Can you summarize what I asked in previous turn?' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R03" "Update user.md via chat" \
  "请根据对话更新user.md：偏好英文、回答简洁。" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message '请根据对话更新user.md：偏好英文、回答简洁。' --with-ai" \
  '"intent": "profile"' '"profile_update"'

run_round "R04" "Profile effect check" \
  "Please reply in one concise English sentence: profile applied." \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'Please reply in one concise English sentence: profile applied.' --with-ai" \
  '"intent": "chat"' '"mode": "ai"'

run_round "R05" "Chat-triggered tool execution" \
  "check for updates" \
  "$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' --message 'check for updates' --with-ai --execute" \
  '"intent": "update"' '"execution"'

run_round "R06" "NL local tool execute" \
  "执行命令: ls data/examples/trajectory" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '执行命令: ls data/examples/trajectory' --execute" \
  '"intent": "local"' '"execute": true'

run_round "R07" "Composite: NL + SRE external + execute" \
  "请基于data-dir data/raw/wuhan_osm分析武汉最适合建商场的前5个地点" \
  "$PY_BIN -m geoclaw_qgis.cli.main nl '请基于data-dir data/raw/wuhan_osm分析武汉最适合建商场的前5个地点' --use-sre --sre-reasoner-mode external --execute" \
  '"sre_enabled": true' '"execute": true'

run_round "R08" "Skill listing" \
  "列出可用skills" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --list" \
  'mall_site_selection_qgis' 'network_trackintel_skill'

run_round "R09" "Pipeline skill + AI summary" \
  "运行mall_site_selection_qgis并输出AI总结" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill mall_site_selection_qgis --skip-download --set location_input=data/outputs/wuhan_location/grid_location.gpkg --set out_dir=$OUT_ROOT/mall_skill --set top_n=5 --with-ai --ai-input 'Summarize top candidates, risks, and field-validation priorities.'" \
  '"skill": "mall_site_selection_qgis"' '"report_source"'

run_round "R10" "Builtin network skill dry-run" \
  "运行network_trackintel_skill dry-run" \
  "$PY_BIN -m geoclaw_qgis.cli.main skill -- --skill network_trackintel_skill --args '--pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv --out-dir $OUT_ROOT/network --dry-run'" \
  '"skill": "network_trackintel_skill"' '"executed_command"'

{
  echo "## Summary"
  echo
  echo "- total_rounds: 10"
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
