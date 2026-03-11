from __future__ import annotations

import datetime as dt
import json
import mimetypes
import os
import re
import subprocess
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from geoclaw_qgis.config import geoclaw_home

MAX_BODY_BYTES = 1024 * 1024
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
PATH_TOKEN_RE = re.compile(r"(?:[A-Za-z]:)?(?:[~.]?[\\/])?[A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,8}")
FILE_LINK_EXT_ALLOW = {
    ".md",
    ".json",
    ".txt",
    ".csv",
    ".geojson",
    ".gpkg",
    ".tif",
    ".tiff",
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".html",
}


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def _utc_iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _sessions_dir() -> Path:
    path = geoclaw_home() / "chat" / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_session_id(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if SESSION_ID_RE.fullmatch(value):
        return value
    value = re.sub(r"[^A-Za-z0-9_-]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if len(value) < 3:
        return ""
    return value[:64]


def _new_session_id() -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"web_{stamp}_{uuid.uuid4().hex[:6]}"


def _session_path(session_id: str) -> Path:
    return _sessions_dir() / f"{session_id}.json"


def _session_payload(session_id: str) -> dict[str, Any]:
    now = _utc_iso_now()
    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "turns": [],
    }


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def create_session(session_id: str = "") -> dict[str, Any]:
    sid = _normalize_session_id(session_id) or _new_session_id()
    path = _session_path(sid)
    if path.exists():
        payload = _safe_read_json(path)
        if payload:
            return {
                "session_id": sid,
                "path": str(path),
                "created": False,
            }
    payload = _session_payload(sid)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "session_id": sid,
        "path": str(path),
        "created": True,
    }


def list_sessions(limit: int = 200) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(_sessions_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[: max(1, int(limit))]:
        payload = _safe_read_json(path)
        sid = str(payload.get("session_id", "")).strip() or path.stem
        turns = payload.get("turns")
        turn_count = len(turns) if isinstance(turns, list) else 0
        rows.append(
            {
                "session_id": sid,
                "turn_count": turn_count,
                "updated_at": str(payload.get("updated_at", "")) or dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "path": str(path),
            }
        )
    return rows


def load_session_detail(session_id: str) -> dict[str, Any]:
    sid = _normalize_session_id(session_id)
    if not sid:
        raise ValueError("invalid session_id")
    path = _session_path(sid)
    if not path.exists():
        raise FileNotFoundError(f"session not found: {sid}")
    payload = _safe_read_json(path)
    turns = payload.get("turns")
    if not isinstance(turns, list):
        turns = []
    return {
        "session_id": sid,
        "turn_count": len(turns),
        "updated_at": str(payload.get("updated_at", "")),
        "created_at": str(payload.get("created_at", "")),
        "turns": turns,
    }


def delete_session(session_id: str) -> dict[str, Any]:
    sid = _normalize_session_id(session_id)
    if not sid:
        raise ValueError("invalid session_id")
    path = _session_path(sid)
    deleted = False
    if path.exists():
        path.unlink()
        deleted = True
    return {
        "session_id": sid,
        "deleted": deleted,
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(raw[i:])
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return {}


def _safe_candidate_token(token: str) -> str:
    return str(token or "").strip().strip("'\"`;,[](){}")


def _candidate_to_path(token: str, *, workspace_root: Path) -> Path | None:
    value = _safe_candidate_token(token)
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return None

    p = Path(value).expanduser()
    if not p.is_absolute():
        p = (workspace_root / p).resolve()
    else:
        p = p.resolve()
    if not p.exists() or not p.is_file():
        return None
    if p.suffix.lower() not in FILE_LINK_EXT_ALLOW:
        return None

    output_root = (workspace_root / "data" / "outputs").resolve()
    examples_root = (workspace_root / "examples").resolve()
    if p.is_relative_to(output_root) or p.is_relative_to(examples_root):
        return p
    return None


def extract_output_links(payload: dict[str, Any], *, workspace_root: Path, extra_text: str = "") -> list[dict[str, str]]:
    candidates: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for v in value.values():
                _walk(v)
            return
        if isinstance(value, list):
            for v in value:
                _walk(v)
            return
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return
            if "/" in text or "\\" in text:
                candidates.add(text)
            for m in PATH_TOKEN_RE.finditer(text):
                candidates.add(m.group(0))

    _walk(payload)
    for m in PATH_TOKEN_RE.finditer(str(extra_text or "")):
        candidates.add(m.group(0))

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for token in sorted(candidates):
        path_obj = _candidate_to_path(token, workspace_root=workspace_root)
        if path_obj is None:
            continue
        abs_path = str(path_obj)
        if abs_path in seen:
            continue
        seen.add(abs_path)
        rows.append(
            {
                "label": path_obj.name,
                "path": abs_path,
                "url": f"/api/file?path={quote(abs_path)}",
            }
        )
    return rows


def run_chat_command(*, message: str, session_id: str, execute: bool, use_sre: bool, timeout: int = 300) -> dict[str, Any]:
    workspace_root = _workspace_root()
    sid = _normalize_session_id(session_id)
    if not sid:
        raise ValueError("invalid session_id")

    cmd = [
        sys.executable,
        "-m",
        "geoclaw_qgis.cli.main",
        "chat",
        "--message",
        message,
        "--session-id",
        sid,
    ]
    if execute:
        cmd.append("--execute")
        if use_sre:
            cmd.append("--use-sre")

    proc = subprocess.run(
        cmd,
        cwd=str(workspace_root),
        check=False,
        capture_output=True,
        text=True,
        timeout=max(10, int(timeout)),
    )
    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    payload = _extract_json_object(stdout)

    execution = payload.get("execution") if isinstance(payload, dict) else None
    tool_triggered = False
    if isinstance(execution, dict):
        tool_triggered = bool(execution.get("command"))
    intent = str(payload.get("intent", "")) if isinstance(payload, dict) else ""

    links = extract_output_links(payload if isinstance(payload, dict) else {}, workspace_root=workspace_root, extra_text=stdout + "\n" + stderr)
    ok = int(proc.returncode) == 0 and isinstance(payload, dict) and bool(payload)

    return {
        "ok": ok,
        "return_code": int(proc.returncode),
        "intent": intent,
        "tool_triggered": tool_triggered,
        "payload": payload,
        "stderr": stderr[-4000:],
        "stdout_tail": stdout[-4000:],
        "output_links": links,
        "command": cmd,
    }


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, status: int, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _file_response(handler: BaseHTTPRequestHandler, status: int, path: Path) -> None:
    data = path.read_bytes()
    mime, _ = mimetypes.guess_type(str(path))
    handler.send_response(status)
    handler.send_header("Content-Type", (mime or "application/octet-stream") + "; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def _parse_json_request(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length_text = str(handler.headers.get("Content-Length", "0")).strip() or "0"
    try:
        length = int(length_text)
    except ValueError as exc:
        raise ValueError("invalid content-length") from exc
    if length < 0 or length > MAX_BODY_BYTES:
        raise ValueError("request body too large")
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid json payload") from exc
    if isinstance(payload, dict):
        return payload
    raise ValueError("json payload must be an object")


def _resolve_download_path(raw_path: str) -> Path:
    token = _safe_candidate_token(unquote(raw_path))
    if not token:
        raise ValueError("empty path")
    p = Path(token).expanduser()
    if not p.is_absolute():
        p = (_workspace_root() / p).resolve()
    else:
        p = p.resolve()
    output_root = (_workspace_root() / "data" / "outputs").resolve()
    examples_root = (_workspace_root() / "examples").resolve()
    if not (p.is_relative_to(output_root) or p.is_relative_to(examples_root)):
        raise PermissionError("path outside allowed output roots")
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"file not found: {p}")
    return p


def _page_html() -> str:
    return """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>GeoClaw Web Trial</title>
  <style>
    :root {
      --bg: #f4f8fb;
      --surface: #ffffff;
      --ink: #1f2933;
      --muted: #5f6c7b;
      --brand: #005f73;
      --accent: #ee9b00;
      --danger: #b00020;
      --ok: #1f8f4a;
      --line: #d8e2ea;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at top right, #d7eff7 0%, var(--bg) 45%, #eef4f7 100%);
      min-height: 100vh;
    }
    .shell {
      max-width: 1280px;
      margin: 0 auto;
      padding: 18px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 14px;
      min-height: 100vh;
    }
    .header {
      background: linear-gradient(135deg, #003845, #005f73);
      color: #fff;
      border-radius: 14px;
      padding: 16px 20px;
      box-shadow: 0 8px 26px rgba(0, 0, 0, 0.14);
    }
    .header h1 { margin: 0; font-size: 22px; letter-spacing: .2px; }
    .meta { margin-top: 8px; font-size: 13px; color: #d8eff6; display: flex; gap: 12px; flex-wrap: wrap; }
    .meta a { color: #ffd166; }
    .layout {
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 14px;
      min-height: 0;
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 6px 20px rgba(31, 41, 51, 0.08);
      min-height: 0;
    }
    .panel h2 { margin: 0; font-size: 16px; }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }
    .session-list {
      max-height: calc(100vh - 270px);
      overflow: auto;
      padding: 10px;
      display: grid;
      gap: 8px;
    }
    .session-item {
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      background: #fafcfd;
      cursor: pointer;
      transition: 120ms;
    }
    .session-item:hover { border-color: var(--brand); }
    .session-item.active { border-color: var(--brand); background: #e9f6f9; }
    .sid { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
    .session-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }
    .session-actions { margin-top: 8px; display: flex; justify-content: flex-end; }
    button {
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fff;
      padding: 7px 11px;
      cursor: pointer;
      font-weight: 600;
      color: var(--ink);
    }
    button.primary { background: var(--brand); color: #fff; border-color: var(--brand); }
    button.warn { border-color: var(--danger); color: var(--danger); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .chat-panel {
      display: grid;
      grid-template-rows: auto 1fr auto;
      min-height: 0;
    }
    .status-bar {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-size: 12px;
    }
    .chip {
      border-radius: 999px;
      padding: 4px 10px;
      border: 1px solid var(--line);
      background: #f5f9fb;
    }
    .chat-scroll {
      padding: 16px;
      overflow: auto;
      display: grid;
      gap: 12px;
      background: linear-gradient(180deg, #fbfeff 0%, #f6fafc 100%);
    }
    .msg {
      max-width: 86%;
      border-radius: 12px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      white-space: pre-wrap;
      line-height: 1.45;
    }
    .msg.user { justify-self: end; background: #dff2f7; border-color: #b3ddea; }
    .msg.assistant { justify-self: start; background: #ffffff; }
    .msg.meta { justify-self: center; max-width: 100%; font-size: 12px; color: var(--muted); }
    .composer {
      border-top: 1px solid var(--line);
      padding: 12px;
      display: grid;
      gap: 10px;
    }
    textarea {
      width: 100%;
      min-height: 92px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      font: inherit;
    }
    .composer-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }
    .links {
      display: grid;
      gap: 6px;
      font-size: 13px;
    }
    .links a { color: #0b4f6c; }
    .error {
      color: var(--danger);
      font-size: 13px;
      background: #ffedf0;
      border: 1px solid #ffc9d1;
      border-radius: 10px;
      padding: 8px 10px;
      display: none;
    }
    .ok { color: var(--ok); }
    @media (max-width: 980px) {
      .layout { grid-template-columns: 1fr; }
      .session-list { max-height: 210px; }
      .chat-panel { min-height: 72vh; }
    }
  </style>
</head>
<body>
  <div class=\"shell\">
    <header class=\"header\">
      <h1>GeoClaw Web Trial</h1>
      <div class=\"meta\">
        <span>团队试用版目标周期: <strong>3-5 天</strong></span>
        <span>Copyright (c) UrbanComp Lab @ China University of Geosciences (Wuhan)</span>
        <span>GitHub: <a target=\"_blank\" href=\"https://github.com/whuyao/GeoClaw-OpenAI\">whuyao/GeoClaw-OpenAI</a></span>
      </div>
    </header>

    <section class=\"layout\">
      <aside class=\"panel\">
        <div class=\"panel-head\">
          <h2>会话管理</h2>
          <button id=\"btn-new\" class=\"primary\">新建会话</button>
        </div>
        <div class=\"session-list\" id=\"session-list\"></div>
      </aside>

      <main class=\"panel chat-panel\">
        <div class=\"status-bar\" id=\"status\">
          <span class=\"chip\" id=\"st-session\">Session: -</span>
          <span class=\"chip\" id=\"st-intent\">Intent: -</span>
          <span class=\"chip\" id=\"st-tool\">工具触发: -</span>
          <span class=\"chip\" id=\"st-rc\">Return code: -</span>
        </div>
        <div class=\"chat-scroll\" id=\"chat-scroll\">
          <div class=\"msg meta\">提示: 输入自然语言。默认使用 AI 聊天；勾选执行后会在可执行请求时触发工具。</div>
        </div>
        <div class=\"composer\">
          <div class=\"error\" id=\"error-box\"></div>
          <textarea id=\"input\" placeholder=\"例如: 请你下载景德镇的数据，并分析最适合建设商场的前5个地址，输出报告\"></textarea>
          <div class=\"composer-row\">
            <label><input type=\"checkbox\" id=\"execute\" checked /> 执行可操作请求</label>
            <label><input type=\"checkbox\" id=\"use-sre\" /> 启用 SRE 路由</label>
            <div style=\"display:flex; gap:8px;\">
              <button id=\"btn-retry\" class=\"warn\" disabled>重试失败请求</button>
              <button id=\"btn-send\" class=\"primary\">发送</button>
            </div>
          </div>
          <div class=\"links\" id=\"links\"></div>
        </div>
      </main>
    </section>
  </div>

<script>
const state = {
  sessionId: "",
  loading: false,
  lastFailedRequest: null,
};

function byId(id) { return document.getElementById(id); }

function setStatus({intent = "-", tool = "-", rc = "-"} = {}) {
  byId("st-session").textContent = `Session: ${state.sessionId || "-"}`;
  byId("st-intent").textContent = `Intent: ${intent}`;
  byId("st-tool").textContent = `工具触发: ${tool}`;
  byId("st-rc").textContent = `Return code: ${rc}`;
}

function setError(text) {
  const box = byId("error-box");
  if (!text) {
    box.style.display = "none";
    box.textContent = "";
    return;
  }
  box.style.display = "block";
  box.textContent = text;
}

function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  wrap.textContent = text || "";
  byId("chat-scroll").appendChild(wrap);
  byId("chat-scroll").scrollTop = byId("chat-scroll").scrollHeight;
}

function renderLinks(links) {
  const box = byId("links");
  box.innerHTML = "";
  if (!Array.isArray(links) || links.length === 0) {
    return;
  }
  const title = document.createElement("div");
  title.className = "ok";
  title.textContent = "报告/输出文件:";
  box.appendChild(title);
  for (const item of links) {
    const a = document.createElement("a");
    a.href = item.url;
    a.target = "_blank";
    a.textContent = `${item.label} (${item.path})`;
    box.appendChild(a);
  }
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const text = await res.text();
  let payload = {};
  try { payload = text ? JSON.parse(text) : {}; } catch (_) { payload = {error: text}; }
  if (!res.ok) {
    throw new Error(payload.error || `HTTP ${res.status}`);
  }
  return payload;
}

function sessionCard(s) {
  const node = document.createElement("div");
  node.className = "session-item" + (s.session_id === state.sessionId ? " active" : "");
  node.innerHTML = `
    <div class="sid">${s.session_id}</div>
    <div class="session-sub">轮次: ${s.turn_count} | 更新: ${s.updated_at || "-"}</div>
    <div class="session-actions"><button class="warn" data-del="${s.session_id}">删除</button></div>
  `;
  node.addEventListener("click", async (e) => {
    const del = e.target && e.target.getAttribute("data-del");
    if (del) {
      e.stopPropagation();
      await removeSession(del);
      return;
    }
    await chooseSession(s.session_id);
  });
  return node;
}

async function loadSessions() {
  const payload = await api("/api/sessions");
  const box = byId("session-list");
  box.innerHTML = "";
  const list = payload.sessions || [];
  list.forEach((s) => box.appendChild(sessionCard(s)));
  if (!state.sessionId && list.length > 0) {
    await chooseSession(list[0].session_id);
  }
}

async function createSession() {
  const payload = await api("/api/sessions", {method: "POST", body: JSON.stringify({})});
  state.sessionId = payload.session_id;
  await loadSessions();
  setStatus();
}

async function chooseSession(sessionId) {
  state.sessionId = sessionId;
  const payload = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  byId("chat-scroll").innerHTML = "";
  const turns = payload.turns || [];
  if (turns.length === 0) {
    addMessage("meta", "当前会话还没有消息。开始提问即可。");
  } else {
    for (const t of turns) {
      addMessage("user", t.user || "");
      addMessage("assistant", t.assistant || "");
    }
  }
  setStatus();
  await loadSessions();
}

async function removeSession(sessionId) {
  await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {method: "DELETE"});
  if (state.sessionId === sessionId) {
    state.sessionId = "";
    byId("chat-scroll").innerHTML = "";
    addMessage("meta", "会话已删除，请新建会话。");
  }
  await loadSessions();
  setStatus();
}

async function sendMessage(message, isRetry = false) {
  if (!message || state.loading) return;
  if (!state.sessionId) {
    await createSession();
  }
  state.loading = true;
  byId("btn-send").disabled = true;
  byId("btn-retry").disabled = true;
  setError("");

  const req = {
    session_id: state.sessionId,
    message,
    execute: !!byId("execute").checked,
    use_sre: !!byId("use-sre").checked,
  };
  if (!isRetry) addMessage("user", message);

  try {
    const result = await api("/api/chat", {method: "POST", body: JSON.stringify(req)});
    const p = result.payload || {};
    const chat = p.chat || {};
    addMessage("assistant", chat.reply || "(empty)");
    setStatus({
      intent: result.intent || p.intent || "-",
      tool: result.tool_triggered ? "是" : "否",
      rc: String(result.return_code),
    });
    renderLinks(result.output_links || []);
    state.lastFailedRequest = null;
  } catch (err) {
    const msg = String(err && err.message ? err.message : err);
    setError(`请求失败: ${msg}`);
    addMessage("assistant", `请求失败。可点击“重试失败请求”。\n错误: ${msg}`);
    state.lastFailedRequest = req;
    byId("btn-retry").disabled = false;
  } finally {
    state.loading = false;
    byId("btn-send").disabled = false;
    await loadSessions();
  }
}

byId("btn-new").addEventListener("click", async () => {
  try { await createSession(); } catch (err) { setError(String(err)); }
});

byId("btn-send").addEventListener("click", async () => {
  const input = byId("input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  await sendMessage(text);
});

byId("btn-retry").addEventListener("click", async () => {
  if (!state.lastFailedRequest) return;
  await sendMessage(state.lastFailedRequest.message, true);
});

byId("input").addEventListener("keydown", async (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    const input = byId("input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    await sendMessage(text);
  }
});

(async function init() {
  try {
    await loadSessions();
    if (!state.sessionId) await createSession();
    setStatus();
  } catch (err) {
    setError(String(err));
  }
})();
</script>
</body>
</html>"""


class GeoClawWebHandler(BaseHTTPRequestHandler):
    server_version = "GeoClawWeb/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[web] " + fmt % args + "\n")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            _html_response(self, 200, _page_html())
            return
        if path == "/api/health":
            _json_response(self, 200, {"ok": True, "service": "geoclaw-web"})
            return
        if path == "/api/sessions":
            _json_response(self, 200, {"sessions": list_sessions()})
            return
        if path.startswith("/api/sessions/"):
            sid = unquote(path.split("/api/sessions/", 1)[1])
            try:
                _json_response(self, 200, load_session_detail(sid))
            except Exception as exc:
                _json_response(self, 404, {"error": str(exc)})
            return
        if path == "/api/file":
            qs = parse_qs(parsed.query)
            raw_path = str((qs.get("path") or [""])[0]).strip()
            try:
                file_path = _resolve_download_path(raw_path)
                _file_response(self, 200, file_path)
            except Exception as exc:
                _json_response(self, 400, {"error": str(exc)})
            return
        _json_response(self, 404, {"error": f"not found: {path}"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/sessions":
            try:
                payload = _parse_json_request(self)
                sid = str(payload.get("session_id", "")).strip()
                created = create_session(sid)
                _json_response(self, 200, created)
            except Exception as exc:
                _json_response(self, 400, {"error": str(exc)})
            return
        if parsed.path == "/api/chat":
            try:
                payload = _parse_json_request(self)
                message = str(payload.get("message", "")).strip()
                if not message:
                    raise ValueError("message is required")
                sid = str(payload.get("session_id", "")).strip()
                if not _normalize_session_id(sid):
                    created = create_session("")
                    sid = str(created["session_id"])
                else:
                    create_session(sid)
                execute = bool(payload.get("execute", True))
                use_sre = bool(payload.get("use_sre", False))
                result = run_chat_command(message=message, session_id=sid, execute=execute, use_sre=use_sre)
                result["session_id"] = sid
                code = 200 if result.get("ok") else 500
                _json_response(self, code, result)
            except Exception as exc:
                _json_response(self, 500, {"error": str(exc), "can_retry": True})
            return
        _json_response(self, 404, {"error": f"not found: {parsed.path}"})

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/sessions/"):
            sid = unquote(parsed.path.split("/api/sessions/", 1)[1])
            try:
                _json_response(self, 200, delete_session(sid))
            except Exception as exc:
                _json_response(self, 400, {"error": str(exc)})
            return
        _json_response(self, 404, {"error": f"not found: {parsed.path}"})


def run_web_server(*, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> int:
    server = ThreadingHTTPServer((host, int(port)), GeoClawWebHandler)
    url = f"http://{host}:{port}"
    print(json.dumps({"service": "geoclaw-web", "url": url, "workspace": str(_workspace_root())}, ensure_ascii=False, indent=2))
    if open_browser:
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


__all__ = [
    "create_session",
    "delete_session",
    "extract_output_links",
    "list_sessions",
    "load_session_detail",
    "run_chat_command",
    "run_web_server",
]
