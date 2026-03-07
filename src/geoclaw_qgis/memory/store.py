from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from geoclaw_qgis.config import geoclaw_home


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class TaskMemoryStore:
    """Persist short-term task memory and reviewed long-term memory."""

    def __init__(self) -> None:
        self._root = geoclaw_home() / "memory"
        self._short_dir = self._root / "short"
        self._long_file = self._root / "long_term.jsonl"
        self._ensure_paths()

    @property
    def short_dir(self) -> Path:
        return self._short_dir

    @property
    def long_file(self) -> Path:
        return self._long_file

    def _ensure_paths(self) -> None:
        self._short_dir.mkdir(parents=True, exist_ok=True)
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
        }
        self._write_short(task_id, payload)
        return task_id

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

        return {
            "reviewed_at": _utc_now(),
            "summary": summary,
            "lessons": lessons,
            "next_actions": actions,
        }
