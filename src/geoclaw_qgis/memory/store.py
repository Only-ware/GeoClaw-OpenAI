from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from geoclaw_qgis.config import geoclaw_home
from geoclaw_qgis.profile import SessionProfile, load_session_profile
from .retrieval import best_matches


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _safe_session_key(raw: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(raw or "").strip())
    text = text.strip("._-")
    return text or "adhoc"


def _clip_text(text: str, *, max_chars: int = 240) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max(1, max_chars - 3)] + "..."


class TaskMemoryStore:
    """Persist short-term task memory and reviewed long-term memory."""

    def __init__(self, session_profile: SessionProfile | None = None) -> None:
        self._root = geoclaw_home() / "memory"
        self._short_dir = self._root / "short"
        self._archive_short_dir = self._root / "archive" / "short"
        self._long_file = self._root / "long_term.jsonl"
        self._session_profile = session_profile
        if self._session_profile is None:
            try:
                self._session_profile = load_session_profile()
            except Exception:
                self._session_profile = None
        self._ensure_paths()

    @property
    def short_dir(self) -> Path:
        return self._short_dir

    @property
    def archive_short_dir(self) -> Path:
        return self._archive_short_dir

    @property
    def long_file(self) -> Path:
        return self._long_file

    def _ensure_paths(self) -> None:
        self._short_dir.mkdir(parents=True, exist_ok=True)
        self._archive_short_dir.mkdir(parents=True, exist_ok=True)
        self._long_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._long_file.exists():
            self._long_file.touch()

    def start_task(self, command: str, argv: list[str], cwd: str) -> str:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        task_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
        payload: dict[str, Any] = {
            "task_id": task_id,
            "command": command,
            "argv": list(argv),
            "cwd": cwd,
            "status": "running",
            "return_code": None,
            "error": "",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "finished_at": "",
            "promoted": False,
            "review": {},
            "profile_snapshot": self._memory_profile_snapshot(),
        }
        self._write_short(task_id, payload)
        return task_id

    def record_chat_turn(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_reply: str,
        intent: str = "chat",
        mode: str = "fallback",
        event_time: str = "",
        cwd: str = "",
    ) -> dict[str, Any]:
        event = _parse_event_time(event_time)
        day = event.strftime("%Y%m%d")
        sid = _safe_session_key(session_id)
        task_id = f"chat-{day}-{sid}"
        path = self._short_path(task_id)
        now_iso = event.isoformat()

        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        else:
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        if not payload:
            payload = {
                "task_id": task_id,
                "command": "chat_daily",
                "argv": [f"--session-id={sid}", f"--day={day}"],
                "cwd": cwd or "",
                "status": "success",
                "return_code": 0,
                "error": "",
                "created_at": now_iso,
                "updated_at": now_iso,
                "finished_at": now_iso,
                "promoted": False,
                "review": {},
                "profile_snapshot": self._memory_profile_snapshot(),
                "extra": {
                    "memory_kind": "chat_daily",
                    "date": day,
                    "session_id": sid,
                },
                "chat_digest": {
                    "turn_count": 0,
                    "intents": [],
                    "modes": [],
                    "recent_turns": [],
                    "last_turn_at": "",
                },
            }

        digest = payload.get("chat_digest")
        if not isinstance(digest, dict):
            digest = {
                "turn_count": 0,
                "intents": [],
                "modes": [],
                "recent_turns": [],
                "last_turn_at": "",
            }
        turn_count = int(digest.get("turn_count", 0)) + 1
        digest["turn_count"] = turn_count
        digest["last_turn_at"] = now_iso

        intents = [str(x).strip() for x in (digest.get("intents") or []) if str(x).strip()]
        if intent and intent not in intents:
            intents.append(intent)
        digest["intents"] = intents[-10:]

        modes = [str(x).strip() for x in (digest.get("modes") or []) if str(x).strip()]
        if mode and mode not in modes:
            modes.append(mode)
        digest["modes"] = modes[-10:]

        turns = [x for x in (digest.get("recent_turns") or []) if isinstance(x, dict)]
        turns.append(
            {
                "ts": now_iso,
                "user": _clip_text(user_message, max_chars=160),
                "assistant": _clip_text(assistant_reply, max_chars=200),
            }
        )
        digest["recent_turns"] = turns[-8:]

        payload["chat_digest"] = digest
        payload["status"] = "success"
        payload["return_code"] = 0
        payload["error"] = ""
        payload["updated_at"] = now_iso
        payload["finished_at"] = now_iso
        if not str(payload.get("created_at", "")).strip():
            payload["created_at"] = now_iso
        if not str(payload.get("cwd", "")).strip():
            payload["cwd"] = cwd or ""

        extra = payload.get("extra")
        if not isinstance(extra, dict):
            extra = {}
        extra.update({"memory_kind": "chat_daily", "date": day, "session_id": sid})
        payload["extra"] = extra

        if not isinstance(payload.get("profile_snapshot"), dict):
            payload["profile_snapshot"] = self._memory_profile_snapshot()

        self._write_short(task_id, payload)
        return payload

    def list_chat_daily(self, *, limit: int = 20, session_id: str = "") -> list[dict[str, Any]]:
        sid = _safe_session_key(session_id) if session_id else ""
        rows: list[dict[str, Any]] = []
        for row in self.list_short(limit=max(200, int(limit) * 6)):
            extra = row.get("extra")
            if not isinstance(extra, dict):
                continue
            if str(extra.get("memory_kind", "")).strip() != "chat_daily":
                continue
            if sid and str(extra.get("session_id", "")).strip() != sid:
                continue
            rows.append(row)
            if len(rows) >= max(1, int(limit)):
                break
        return rows

    def get_chat_daily_digest(self, *, session_id: str) -> dict[str, Any]:
        rows = self.list_chat_daily(limit=1, session_id=session_id)
        if not rows:
            return {}
        row = rows[0]
        digest = row.get("chat_digest")
        if not isinstance(digest, dict):
            return {}
        out = dict(digest)
        out["task_id"] = str(row.get("task_id", ""))
        out["date"] = str((row.get("extra") or {}).get("date", ""))
        return out

    def finish_task(
        self,
        task_id: str,
        return_code: int,
        *,
        error: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._read_short(task_id)
        payload["status"] = "success" if return_code == 0 else "failed"
        payload["return_code"] = int(return_code)
        payload["error"] = error.strip()
        payload["finished_at"] = _utc_now()
        payload["updated_at"] = _utc_now()
        if extra:
            payload["extra"] = {**(payload.get("extra") or {}), **extra}
        self._write_short(task_id, payload)
        return payload

    def auto_review_to_long(self, task_id: str) -> dict[str, Any]:
        task = self._read_short(task_id)
        review = self._build_review(task)
        long_payload: dict[str, Any] = {
            "task_id": task["task_id"],
            "command": task.get("command", ""),
            "argv": task.get("argv", []),
            "cwd": task.get("cwd", ""),
            "status": task.get("status", ""),
            "return_code": task.get("return_code"),
            "created_at": task.get("created_at", ""),
            "finished_at": task.get("finished_at", ""),
            "reviewed_at": review["reviewed_at"],
            "summary": review["summary"],
            "lessons": review["lessons"],
            "next_actions": review["next_actions"],
        }
        with self._long_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(long_payload, ensure_ascii=False) + "\n")

        task["promoted"] = True
        task["review"] = review
        task["updated_at"] = _utc_now()
        self._write_short(task_id, task)
        return long_payload

    def review_task_to_long(
        self,
        task_id: str,
        *,
        summary: str = "",
        lessons: list[str] | None = None,
        next_actions: list[str] | None = None,
    ) -> dict[str, Any]:
        task = self._read_short(task_id)
        auto = self._build_review(task)
        custom_summary = summary.strip()
        custom_lessons = [x.strip() for x in (lessons or []) if x.strip()]
        custom_actions = [x.strip() for x in (next_actions or []) if x.strip()]

        merged = {
            "reviewed_at": _utc_now(),
            "summary": custom_summary or auto["summary"],
            "lessons": custom_lessons or auto["lessons"],
            "next_actions": custom_actions or auto["next_actions"],
        }
        long_payload: dict[str, Any] = {
            "task_id": task["task_id"],
            "command": task.get("command", ""),
            "argv": task.get("argv", []),
            "cwd": task.get("cwd", ""),
            "status": task.get("status", ""),
            "return_code": task.get("return_code"),
            "created_at": task.get("created_at", ""),
            "finished_at": task.get("finished_at", ""),
            "reviewed_at": merged["reviewed_at"],
            "summary": merged["summary"],
            "lessons": merged["lessons"],
            "next_actions": merged["next_actions"],
        }
        with self._long_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(long_payload, ensure_ascii=False) + "\n")

        task["promoted"] = True
        task["review"] = merged
        task["updated_at"] = _utc_now()
        self._write_short(task_id, task)
        return long_payload

    def get_short(self, task_id: str) -> dict[str, Any]:
        return self._read_short(task_id)

    def list_short(self, *, limit: int = 20, status: str = "") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self._short_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            row_status = str(payload.get("status", ""))
            if status and row_status != status:
                continue
            rows.append(payload)
            if len(rows) >= max(1, limit):
                break
        return rows

    def list_long(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self._long_file.exists():
            return rows
        for raw in reversed(self._long_file.read_text(encoding="utf-8").splitlines()):
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            rows.append(payload)
            if len(rows) >= max(1, limit):
                break
        return rows

    def list_archive_short(self, *, limit: int = 20, status: str = "") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self._archive_short_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            row_status = str(payload.get("status", ""))
            if status and row_status != status:
                continue
            rows.append(payload)
            if len(rows) >= max(1, limit):
                break
        return rows

    def archive_short(
        self,
        *,
        before_days: int = 7,
        status: str = "",
        include_running: bool = False,
    ) -> dict[str, Any]:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=max(0, int(before_days)))
        moved = 0
        skipped = 0
        archived_ids: list[str] = []

        for path in sorted(self._short_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(payload, dict):
                skipped += 1
                continue

            row_status = str(payload.get("status", ""))
            if status and row_status != status:
                skipped += 1
                continue
            if not include_running and row_status == "running":
                skipped += 1
                continue

            ts = str(payload.get("finished_at", "") or payload.get("updated_at", "") or payload.get("created_at", ""))
            try:
                item_time = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                skipped += 1
                continue
            if item_time > cutoff:
                skipped += 1
                continue

            dst = self._archive_short_dir / path.name
            if dst.exists():
                dst = self._archive_short_dir / f"{path.stem}-{uuid.uuid4().hex[:6]}.json"
            shutil.move(str(path), str(dst))
            moved += 1
            archived_ids.append(str(payload.get("task_id", path.stem)))

        return {
            "moved": moved,
            "skipped": skipped,
            "before_days": int(before_days),
            "status_filter": status,
            "archive_dir": str(self._archive_short_dir),
            "archived_task_ids": archived_ids,
        }

    def search_memory(
        self,
        *,
        query: str,
        scope: str = "long",
        top_k: int = 5,
        min_score: float = 0.15,
    ) -> list[dict[str, Any]]:
        scope_text = scope.strip().lower() or "long"
        if scope_text not in {"short", "long", "all", "archive"}:
            raise ValueError("scope must be one of: short, long, archive, all")

        items: list[dict[str, object]] = []
        if scope_text in {"short", "all"}:
            for row in self.list_short(limit=500):
                text = self._build_search_text(row, source="short")
                items.append({"source": "short", "task_id": row.get("task_id", ""), "search_text": text, "payload": row})

        if scope_text in {"archive", "all"}:
            for row in self.list_archive_short(limit=1000):
                text = self._build_search_text(row, source="archive")
                items.append({"source": "archive", "task_id": row.get("task_id", ""), "search_text": text, "payload": row})

        if scope_text in {"long", "all"}:
            for row in self.list_long(limit=1000):
                text = self._build_search_text(row, source="long")
                items.append({"source": "long", "task_id": row.get("task_id", ""), "search_text": text, "payload": row})

        return best_matches(query, items, top_k=top_k, min_score=min_score)

    def count_short(self) -> int:
        return len(list(self._short_dir.glob("*.json")))

    def count_long(self) -> int:
        if not self._long_file.exists():
            return 0
        return sum(1 for x in self._long_file.read_text(encoding="utf-8").splitlines() if x.strip())

    def _short_path(self, task_id: str) -> Path:
        return self._short_dir / f"{task_id}.json"

    def _read_short(self, task_id: str) -> dict[str, Any]:
        path = self._short_path(task_id)
        if not path.exists():
            raise FileNotFoundError(f"short memory task not found: {task_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"invalid short memory format: {path}")
        return payload

    def _write_short(self, task_id: str, payload: dict[str, Any]) -> None:
        path = self._short_path(task_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_review(self, task: dict[str, Any]) -> dict[str, Any]:
        command = str(task.get("command", "task"))
        status = str(task.get("status", "unknown"))
        return_code = task.get("return_code")
        error = str(task.get("error", "")).strip()

        if status == "success":
            summary = f"Command '{command}' completed successfully."
            lessons = ["Current parameters and environment are runnable and reproducible."]
            actions = ["Keep output artifacts and logs for future comparison."]
        else:
            summary = f"Command '{command}' failed with return code {return_code}."
            lessons = ["Failure information has been captured in short-term memory."]
            actions = ["Check CLI output and rerun after fixing environment or parameters."]
            if error:
                actions.append(f"Primary error: {error}")

        profile_ctx = self._memory_profile_snapshot()
        repro = profile_ctx.get("reproducibility_expectations") or []
        constraints = profile_ctx.get("long_term_constraints") or []
        if isinstance(repro, list):
            for item in repro[:2]:
                lessons.append(f"Profile reproducibility expectation: {item}")
        if status != "success" and isinstance(constraints, list):
            for item in constraints[:2]:
                actions.append(f"Profile long-term constraint reminder: {item}")

        return {
            "reviewed_at": _utc_now(),
            "summary": summary,
            "lessons": lessons,
            "next_actions": actions,
        }

    def _build_search_text(self, payload: dict[str, Any], *, source: str) -> str:
        parts: list[str] = [
            str(source),
            str(payload.get("task_id", "")),
            str(payload.get("command", "")),
            " ".join(str(x) for x in (payload.get("argv") or [])),
            str(payload.get("status", "")),
            str(payload.get("error", "")),
            str(payload.get("summary", "")),
        ]
        review = payload.get("review")
        if isinstance(review, dict):
            parts.append(str(review.get("summary", "")))
            parts.extend(str(x) for x in (review.get("lessons") or []))
            parts.extend(str(x) for x in (review.get("next_actions") or []))
        parts.extend(str(x) for x in (payload.get("lessons") or []))
        parts.extend(str(x) for x in (payload.get("next_actions") or []))
        snapshot = payload.get("profile_snapshot")
        if isinstance(snapshot, dict):
            parts.append(str(snapshot.get("user_role", "")))
            parts.append(str(snapshot.get("preferred_tone", "")))
            parts.extend(str(x) for x in (snapshot.get("reproducibility_expectations") or []))
            parts.extend(str(x) for x in (snapshot.get("truthfulness_rules") or []))
        return "\n".join(x for x in parts if x.strip())

    def _memory_profile_snapshot(self) -> dict[str, Any]:
        if self._session_profile is None:
            return {}
        return self._session_profile.memory_context()


def _parse_event_time(raw: str) -> dt.datetime:
    text = str(raw or "").strip()
    if not text:
        return dt.datetime.now(dt.timezone.utc)
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return dt.datetime.now(dt.timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)
