from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path

from geoclaw_qgis.memory import TaskMemoryStore


class TestMemoryStore(unittest.TestCase):
    def test_archive_and_vector_search(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["GEOCLAW_OPENAI_HOME"] = str(Path(tmp) / "home")
                store = TaskMemoryStore()

                task_a = store.start_task("operator", ["--algorithm", "native:buffer"], cwd=tmp)
                short_a = store.get_short(task_a)
                self.assertIn("profile_snapshot", short_a)
                store.finish_task(task_a, 0, error="")
                store.auto_review_to_long(task_a)

                task_b = store.start_task("run", ["--case", "site_selection"], cwd=tmp)
                store.finish_task(task_b, 1, error="missing input")

                old_ts = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()
                short_b = store.short_dir / f"{task_b}.json"
                payload = json.loads(short_b.read_text(encoding="utf-8"))
                payload["finished_at"] = old_ts
                payload["updated_at"] = old_ts
                short_b.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

                archived = store.archive_short(before_days=7, status="failed")
                self.assertEqual(int(archived.get("moved", 0)), 1)
                self.assertGreaterEqual(int(archived.get("skipped", 0)), 0)
                self.assertEqual(store.count_short(), 1)

                hits = store.search_memory(query="buffer 分析", scope="all", top_k=3, min_score=0.0)
                self.assertGreaterEqual(len(hits), 1)
                self.assertIn("score", hits[0])
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_record_chat_turn_daily_digest(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["GEOCLAW_OPENAI_HOME"] = str(Path(tmp) / "home")
                store = TaskMemoryStore()

                row_a = store.record_chat_turn(
                    session_id="daily_demo",
                    user_message="第一轮：武汉商场选址怎么做",
                    assistant_reply="先确认研究范围和数据。",
                    intent="chat",
                    mode="fallback",
                )
                row_b = store.record_chat_turn(
                    session_id="daily_demo",
                    user_message="第二轮：继续并输出前5个候选点",
                    assistant_reply="已记录，会在 run 工作流中设置 --top-n 5。",
                    intent="run",
                    mode="ai",
                )
                self.assertEqual(row_a.get("task_id"), row_b.get("task_id"))

                digest = store.get_chat_daily_digest(session_id="daily_demo")
                self.assertEqual(int(digest.get("turn_count", 0)), 2)
                intents = [str(x) for x in (digest.get("intents") or [])]
                self.assertIn("chat", intents)
                self.assertIn("run", intents)
                turns = [x for x in (digest.get("recent_turns") or []) if isinstance(x, dict)]
                self.assertEqual(len(turns), 2)
        finally:
            os.environ.clear()
            os.environ.update(old_env)


if __name__ == "__main__":
    unittest.main()
