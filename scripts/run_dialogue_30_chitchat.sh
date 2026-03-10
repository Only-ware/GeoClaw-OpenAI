#!/usr/bin/env bash
set -u

ROOT="/Volumes/Yaoy/project/AI-Agents"
cd "$ROOT"
PY_BIN="$(command -v python3)"

if [[ -z "${GEOCLAW_AI_API_KEY:-}" && -z "${GEOCLAW_OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: GEOCLAW_AI_API_KEY (or GEOCLAW_OPENAI_API_KEY) is required for AI chat."
  exit 2
fi

KEY_CHECK="${GEOCLAW_AI_API_KEY:-${GEOCLAW_OPENAI_API_KEY:-}}"
if [[ "$KEY_CHECK" == *"test-key"* || "$KEY_CHECK" == "dummy" || "$KEY_CHECK" == "placeholder" ]]; then
  echo "ERROR: Detected placeholder API key. Please export a real AI key before running."
  exit 2
fi

TS="$(date +%Y%m%d_%H%M%S)"
DAY="${TS%%_*}"
OUT_ROOT="data/outputs/dialogue_chitchat30_${TS}"
RAW_DIR="$OUT_ROOT/raw"
REPORT="$OUT_ROOT/dialogue_report.md"
EASY_REPORT="$OUT_ROOT/dialogue_report_easy.md"
META="$OUT_ROOT/rounds_meta.tsv"
SESSION="dialogue_chitchat30_${TS}"
TMP_HOME="/tmp/geoclaw_dialogue_chitchat30_${TS}"
EXAMPLE_REPORT="examples/chat/dialogue_suite_30_rounds_chitchat_${DAY}.md"

mkdir -p "$RAW_DIR" "$TMP_HOME" "$(dirname "$EXAMPLE_REPORT")"

export GEOCLAW_OPENAI_HOME="$TMP_HOME"
export PYTHONPATH="${PYTHONPATH:-}:$ROOT/src"

PASS=0
FAIL=0

cat > "$META" <<EOF
id	user_prompt	raw_log
EOF

append_report_header() {
  cat > "$REPORT" <<MD
# GeoClaw 30-Round Continuous Chit-chat Report

- generated_at: $(date -Iseconds)
- workspace: $ROOT
- output_root: $OUT_ROOT
- session_id: $SESSION
- mode: AI chat (\`--with-ai\`)
- objective: verify 30-round continuous conversation without task execution trigger
- isolated_home: $TMP_HOME

## Validation Rules

1. Every round must keep \`intent=chat\`.
2. No round should contain workflow execution payload.
3. Session should persist and turn count should increase to 30.

MD
}

parse_and_assert_round() {
  local log_path="$1"
  "$PY_BIN" - "$log_path" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="ignore")
dec = json.JSONDecoder()
obj = None
i = 0
while i < len(text):
    j = text.find("{", i)
    if j < 0:
        break
    try:
        parsed, end = dec.raw_decode(text[j:])
    except Exception:
        i = j + 1
        continue
    if isinstance(parsed, dict):
        obj = parsed
        break
    i = j + end

if not isinstance(obj, dict):
    print("PARSE_ERROR\t\t\t\t")
    sys.exit(10)

intent = str(obj.get("intent", "")).strip()
mode = str((obj.get("chat") or {}).get("mode", "")).strip()
reply = str((obj.get("chat") or {}).get("reply", "")).replace("\n", " ").strip()
reply = (reply[:140] + "...") if len(reply) > 143 else reply
session = obj.get("session") if isinstance(obj.get("session"), dict) else {}
session_turns = int(session.get("turns", 0) or 0)
session_path = str(session.get("path", "")).strip()
chat_memory = obj.get("chat_memory") if isinstance(obj.get("chat_memory"), dict) else {}
memory_turns = int(chat_memory.get("turn_count", 0) or 0)
memory_task = str(chat_memory.get("task_id", "")).strip()

if intent != "chat":
    print(f"BAD_INTENT\t{intent}\t{mode}\t{session_turns}\t{memory_turns}\t{reply}")
    sys.exit(11)
if mode != "ai":
    print(f"BAD_MODE\t{intent}\t{mode}\t{session_turns}\t{memory_turns}\t{reply}")
    sys.exit(13)
if "execution" in obj:
    print(f"UNEXPECTED_EXEC\t{intent}\t{mode}\t{session_turns}\t{memory_turns}\t{reply}")
    sys.exit(12)

print(
    "OK\t"
    + "\t".join(
        [
            intent,
            mode,
            str(session_turns),
            str(memory_turns),
            session_path,
            memory_task,
            reply,
        ]
    )
)
PY
}

run_round() {
  local id="$1"
  local user_msg="$2"
  local extra="$3"
  local out="$RAW_DIR/${id}.log"
  local cmd="$PY_BIN -m geoclaw_qgis.cli.main chat --session-id '$SESSION' $extra --message '$user_msg' --with-ai"
  local rc=0

  echo "[$id] $user_msg"
  eval "$cmd" >"$out" 2>&1 || rc=$?

  local parsed=""
  local status="PASS"
  if [[ $rc -ne 0 ]]; then
    status="FAIL(rc=$rc)"
  else
    parsed="$(parse_and_assert_round "$out" 2>/dev/null)" || status="FAIL(assert)"
  fi

  if [[ "$status" == "PASS" ]]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi

  printf "%s\t%s\t%s\n" "$id" "$user_msg" "$out" >> "$META"

  {
    echo "## $id"
    echo
    echo "- Q: $user_msg"
    echo "- command:"
    echo '```bash'
    echo "$cmd"
    echo '```'
    echo "- status: $status"
    if [[ -n "$parsed" ]]; then
      local p_status p_intent p_mode p_session_turns p_memory_turns p_session_path p_memory_task p_reply
      IFS=$'\t' read -r p_status p_intent p_mode p_session_turns p_memory_turns p_session_path p_memory_task p_reply <<< "$parsed"
      if [[ "$p_status" == "OK" ]]; then
        echo "- A: $p_reply"
        echo "- process: intent=$p_intent, mode=$p_mode, execution=none, session_turns=$p_session_turns, memory_turns=$p_memory_turns"
        echo "- outputs:"
        echo "  - raw_log: $out"
        echo "  - session_file: $p_session_path"
        echo "  - chat_daily_memory: $p_memory_task"
      else
        echo "- A: $p_reply"
        echo "- process: parse/assert failed (${p_status}), detected intent=$p_intent, mode=$p_mode"
        echo "- outputs:"
        echo "  - raw_log: $out"
      fi
    else
      echo "- A: (parse failed)"
      echo "- process: parse/assert failed"
      echo "- outputs:"
      echo "  - raw_log: $out"
    fi
    echo
  } >> "$REPORT"
}

append_report_header

run_round "R01" "你好，今天我们先轻松聊聊，你现在的状态如何？" "--new-session"
run_round "R02" "如果我今天只想先整理思路，你会怎么陪我聊？" ""
run_round "R03" "你更擅长简短建议还是详细建议？为什么？" ""
run_round "R04" "请用一句话描述你理解的‘高质量对话’。" ""
run_round "R05" "我有点焦虑，先聊聊怎么把任务拆小可以吗？" ""
run_round "R06" "如果我表达不清楚，你会怎么引导我？" ""
run_round "R07" "你觉得连续对话里最重要的是什么？" ""
run_round "R08" "请给我三个日常沟通的小技巧。" ""
run_round "R09" "你会如何平衡效率和耐心？" ""
run_round "R10" "如果我今天状态一般，你建议怎么推进一点点？" ""
run_round "R11" "请你问我一个能帮助我明确目标的问题。" ""
run_round "R12" "我回答：我希望今天结束前有可见进展。你怎么看？" ""
run_round "R13" "再追问我一个更具体的问题。" ""
run_round "R14" "我回答：我更喜欢先有清单再行动。" ""
run_round "R15" "那你给我一个非常短的清单模板。" ""
run_round "R16" "你能把语气再自然一点、像同事沟通吗？" ""
run_round "R17" "当我说‘卡住了’时，你通常会先做什么？" ""
run_round "R18" "请给一个安抚但不空泛的回复示例。" ""
run_round "R19" "如果我反复纠结细节，你会怎么拉回主线？" ""
run_round "R20" "请总结一下到目前为止我们的聊天风格。" ""
run_round "R21" "我们继续，给我一个适合晚间回顾的提问框架。" ""
run_round "R22" "这个框架能再简化成三问吗？" ""
run_round "R23" "如果我只剩15分钟，你建议我聊什么最值？" ""
run_round "R24" "我想要更有温度一点的表达，你能做到吗？" ""
run_round "R25" "请举例说明‘具体建议’和‘泛泛建议’的差别。" ""
run_round "R26" "再给我一个你认为很实用的沟通句式。" ""
run_round "R27" "假设我现在很累，你会如何一句话回应？" ""
run_round "R28" "我们快结束了，请你先做一个中间小结。" ""
run_round "R29" "最后请给我一句鼓励但务实的话。" ""
run_round "R30" "谢谢，今天就聊到这。请你用两句话收尾。" ""

{
  echo "## Summary"
  echo
  echo "- total_rounds: 30"
  echo "- pass: $PASS"
  echo "- fail: $FAIL"
  echo "- generated_at: $(date -Iseconds)"
  echo "- raw_dir: $RAW_DIR"
  echo "- session_file: $TMP_HOME/chat/sessions/$SESSION.json"
  echo "- chat_daily_memory: $TMP_HOME/memory/short/chat-${DAY}-${SESSION}.json"
  echo
  if [[ $FAIL -gt 0 ]]; then
    echo "Result: FAILED"
  else
    echo "Result: PASSED"
  fi
} >> "$REPORT"

"$PY_BIN" - "$REPORT" "$EASY_REPORT" <<'PY'
import pathlib
import re
import sys

src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore")
out = pathlib.Path(sys.argv[2])

sections = re.split(r"^##\s+", src, flags=re.M)
items = []
for s in sections:
    if not s.strip():
        continue
    head, _, body = s.partition("\n")
    if not head.startswith("R"):
        continue
    rid = head.strip()
    q = re.search(r"^- Q: (.+)$", body, flags=re.M)
    a = re.search(r"^- A: (.+)$", body, flags=re.M)
    p = re.search(r"^- process: (.+)$", body, flags=re.M)
    o = re.findall(r"^\s+- (raw_log|session_file|chat_daily_memory): (.+)$", body, flags=re.M)
    items.append((rid, q.group(1).strip() if q else "", a.group(1).strip() if a else "", p.group(1).strip() if p else "", o))

lines = []
lines.append("# GeoClaw 30轮连续闲聊测试（易读版）")
lines.append("")
lines.append(f"- 轮次: {len(items)}")
lines.append("- 目标: 连续闲聊，不触发任务执行")
lines.append("")
for rid, q, a, p, outs in items:
    lines.append(f"## {rid}")
    lines.append(f"- Q: {q}")
    lines.append(f"- A: {a}")
    lines.append(f"- 过程: {p}")
    lines.append("- 输出路径:")
    for k, v in outs:
        lines.append(f"  - {k}: {v}")
    lines.append("")

summary = re.search(r"## Summary(.+)$", src, flags=re.S)
if summary:
    lines.append("## Summary")
    for ln in summary.group(1).splitlines():
        t = ln.strip()
        if t.startswith("- ") or t.startswith("Result:"):
            lines.append(t)

out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
print(str(out))
PY

cp "$EASY_REPORT" "$EXAMPLE_REPORT"

echo "REPORT=$REPORT"
echo "EASY_REPORT=$EASY_REPORT"
echo "EXAMPLE_REPORT=$EXAMPLE_REPORT"
echo "PASS=$PASS FAIL=$FAIL"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
