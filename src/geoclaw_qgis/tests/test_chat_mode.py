from __future__ import annotations

import argparse
import importlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from geoclaw_qgis.memory import TaskMemoryStore
from geoclaw_qgis.profile import ensure_profile_layers
import geoclaw_qgis.profile.layers as profile_layers


cli_main = importlib.import_module("geoclaw_qgis.cli.main")


class TestChatMode(unittest.TestCase):
    def setUp(self) -> None:
        self._old_allow_no_ai = os.environ.get("GEOCLAW_ALLOW_NO_AI_CHAT")
        os.environ["GEOCLAW_ALLOW_NO_AI_CHAT"] = "1"

    def tearDown(self) -> None:
        if self._old_allow_no_ai is None:
            os.environ.pop("GEOCLAW_ALLOW_NO_AI_CHAT", None)
        else:
            os.environ["GEOCLAW_ALLOW_NO_AI_CHAT"] = self._old_allow_no_ai

    def test_chat_fallback_includes_suggestions(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["GEOCLAW_OPENAI_HOME"] = os.path.join(tmp, "home")
                ensure_profile_layers()
                cli_main._SESSION_PROFILE = None

                args = argparse.Namespace(
                    message=["我运行失败了，提示报错怎么办"],
                    message_opt="",
                    with_ai=False,
                    no_ai=True,
                )
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cli_main.cmd_chat(args)
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue())
                self.assertIn("chat", payload)
                chat = payload["chat"]
                self.assertEqual(chat["mode"], "fallback")
                self.assertTrue(len(chat["suggestions"]) > 0)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            cli_main._SESSION_PROFILE = None

    def test_chat_fallback_identity_answer_is_stable(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["GEOCLAW_OPENAI_HOME"] = os.path.join(tmp, "home")
                ensure_profile_layers()
                cli_main._SESSION_PROFILE = None

                args = argparse.Namespace(
                    message=["GeoClaw是什么？谁开发的？主要功能和参考文件有哪些？"],
                    message_opt="",
                    with_ai=False,
                    no_ai=True,
                    execute=False,
                    use_sre=False,
                    sre_report_out="",
                    interactive=False,
                    session_id="",
                    new_session=False,
                    max_history_turns=8,
                )
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cli_main.cmd_chat(args)
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue())
                reply = str(payload["chat"]["reply"])
                self.assertIn("GeoClaw-OpenAI", reply)
                self.assertIn("UrbanComp Lab @ China University of Geosciences (Wuhan)", reply)
                self.assertIn("QGIS", reply)
                self.assertIn("README.md", reply)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            cli_main._SESSION_PROFILE = None

    def test_chat_ai_system_prompt_contains_identity_guardrail(self) -> None:
        old_env = dict(os.environ)
        captured: dict[str, str] = {}

        class FakeClient:
            def __init__(self, cfg: object) -> None:
                self.cfg = cfg

            def chat(self, user_prompt: str, system_prompt: str = "") -> str:
                captured["system_prompt"] = system_prompt
                return "ok"

        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["GEOCLAW_OPENAI_HOME"] = os.path.join(tmp, "home")
                ensure_profile_layers()
                cli_main._SESSION_PROFILE = None
                args = argparse.Namespace(
                    message=["hello"],
                    message_opt="",
                    with_ai=True,
                    no_ai=False,
                    execute=False,
                    use_sre=False,
                    sre_report_out="",
                    interactive=False,
                    session_id="",
                    new_session=False,
                    max_history_turns=8,
                )
                buf = io.StringIO()
                with patch.object(cli_main.ExternalAIConfig, "from_env", return_value=object()), patch.object(
                    cli_main, "ExternalAIClient", FakeClient
                ), redirect_stdout(buf):
                    rc = cli_main.cmd_chat(args)
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue())
                self.assertEqual(payload["chat"]["mode"], "ai")
                prompt = captured.get("system_prompt", "")
                self.assertIn("Project name: GeoClaw-OpenAI", prompt)
                self.assertIn("Developer: UrbanComp Lab @ China University of Geosciences (Wuhan)", prompt)
                self.assertIn("NOT the Clawpack tsunami/flood simulation package", prompt)
                self.assertIn("Reference files:", prompt)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            cli_main._SESSION_PROFILE = None

    def test_chat_ai_user_prompt_includes_profile_and_memory_context(self) -> None:
        old_env = dict(os.environ)
        captured: dict[str, str] = {}

        class FakeClient:
            def __init__(self, cfg: object) -> None:
                self.cfg = cfg

            def chat(self, user_prompt: str, system_prompt: str = "") -> str:
                captured["system_prompt"] = system_prompt
                captured["user_prompt"] = user_prompt
                return "ok"

        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["GEOCLAW_OPENAI_HOME"] = os.path.join(tmp, "home")
                ensure_profile_layers()
                cli_main._SESSION_PROFILE = None

                store = TaskMemoryStore()
                task_id = store.start_task("run", ["--case", "site_selection"], cwd=tmp)
                store.finish_task(task_id, 0, error="")
                store.auto_review_to_long(task_id)
                store.record_chat_turn(
                    session_id="memory_demo",
                    user_message="上一轮讨论武汉商场选址。",
                    assistant_reply="建议先做可达性和覆盖分析。",
                    intent="chat",
                    mode="fallback",
                )

                args = argparse.Namespace(
                    message=["继续上一次讨论，给我下一步。"],
                    message_opt="",
                    with_ai=True,
                    no_ai=False,
                    execute=False,
                    use_sre=False,
                    sre_report_out="",
                    interactive=False,
                    session_id="memory_demo",
                    new_session=False,
                    max_history_turns=8,
                )
                buf = io.StringIO()
                with patch.object(cli_main.ExternalAIConfig, "from_env", return_value=object()), patch.object(
                    cli_main, "ExternalAIClient", FakeClient
                ), redirect_stdout(buf):
                    rc = cli_main.cmd_chat(args)
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue())
                self.assertEqual(payload["chat"]["mode"], "ai")

                user_prompt = captured.get("user_prompt", "")
                self.assertIn("[Profile Context]", user_prompt)
                self.assertIn("[Memory Context]", user_prompt)
                self.assertIn("Recent reviewed memories", user_prompt)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            cli_main._SESSION_PROFILE = None

    def test_local_command_execution(self) -> None:
        args = argparse.Namespace(cmd="echo geoclaw_local_ok", cwd="", timeout=10, shell=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main.cmd_local(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["return_code"], 0)
        self.assertIn("geoclaw_local_ok", payload["stdout"])

    def test_mask_api_key(self) -> None:
        self.assertEqual(cli_main._mask_api_key(""), "")
        self.assertEqual(cli_main._mask_api_key("abc"), "a*c")
        self.assertEqual(cli_main._mask_api_key("sk-test-1234567890"), "sk-t***7890")

    def test_chat_no_ai_disabled_by_default(self) -> None:
        old_env = dict(os.environ)
        try:
            os.environ.pop("GEOCLAW_ALLOW_NO_AI_CHAT", None)
            args = argparse.Namespace(
                message=["hello"],
                message_opt="",
                with_ai=False,
                no_ai=True,
                execute=False,
                use_sre=False,
                sre_report_out="",
                interactive=False,
                session_id="",
                new_session=False,
                max_history_turns=8,
            )
            with self.assertRaises(ValueError):
                cli_main.cmd_chat(args)
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_chat_reply_changes_with_profile(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                home = os.path.join(tmp, "home")
                os.environ["GEOCLAW_OPENAI_HOME"] = home
                ensured = ensure_profile_layers()

                # Profile A: concise Chinese, mission A
                with open(ensured["home_user"], "w", encoding="utf-8") as fh:
                    fh.write(
                        "# User.md\n\n"
                        "## Language Preference\n"
                        "Preferred language: Chinese\n\n"
                        "## Communication Style\n"
                        "- concise explanations\n"
                    )
                with open(ensured["home_soul"], "w", encoding="utf-8") as fh:
                    fh.write("# Soul.md\n\n## Mission\nMission A\n")
                cli_main._SESSION_PROFILE = None
                profile_layers._PROFILE_CACHE = None
                args = argparse.Namespace(
                    message=["请帮我看看下一步怎么做"],
                    message_opt="",
                    with_ai=False,
                    no_ai=True,
                    execute=False,
                    use_sre=False,
                    sre_report_out="",
                )
                buf_a = io.StringIO()
                with redirect_stdout(buf_a):
                    rc_a = cli_main.cmd_chat(args)
                self.assertEqual(rc_a, 0)
                payload_a = json.loads(buf_a.getvalue())
                reply_a = str(payload_a["chat"]["reply"])

                # Profile B: detailed English, mission B
                with open(ensured["home_user"], "w", encoding="utf-8") as fh:
                    fh.write(
                        "# User.md\n\n"
                        "## Language Preference\n"
                        "Preferred language: English\n\n"
                        "## Communication Style\n"
                        "- detailed explanations\n"
                    )
                with open(ensured["home_soul"], "w", encoding="utf-8") as fh:
                    fh.write("# Soul.md\n\n## Mission\nMission B\n")
                cli_main._SESSION_PROFILE = None
                profile_layers._PROFILE_CACHE = None
                buf_b = io.StringIO()
                with redirect_stdout(buf_b):
                    rc_b = cli_main.cmd_chat(args)
                self.assertEqual(rc_b, 0)
                payload_b = json.loads(buf_b.getvalue())
                reply_b = str(payload_b["chat"]["reply"])

                self.assertNotEqual(reply_a, reply_b)
                self.assertIn("Practical next step", reply_b)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            cli_main._SESSION_PROFILE = None
            profile_layers._PROFILE_CACHE = None

    def test_chat_can_update_profile_and_hot_reload(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                home = os.path.join(tmp, "home")
                os.environ["GEOCLAW_OPENAI_HOME"] = home
                ensure_profile_layers()
                cli_main._SESSION_PROFILE = None
                profile_layers._PROFILE_CACHE = None

                args = argparse.Namespace(
                    message=["请根据这次对话更新user.md偏好，偏好英文并详细"],
                    message_opt="",
                    with_ai=False,
                    no_ai=True,
                    execute=False,
                    use_sre=False,
                    sre_report_out="",
                    interactive=False,
                    session_id="",
                    new_session=False,
                    max_history_turns=8,
                )
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cli_main.cmd_chat(args)
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue())
                self.assertEqual(payload.get("intent"), "profile")
                profile_update = payload.get("profile_update") or {}
                self.assertTrue(profile_update.get("applied"))
                profile_after = profile_update.get("profile") or {}
                user_after = profile_after.get("user") or {}
                self.assertEqual(user_after.get("preferred_language"), "English")
                self.assertEqual(user_after.get("preferred_tone"), "detailed")
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            cli_main._SESSION_PROFILE = None
            profile_layers._PROFILE_CACHE = None

    def test_mall_query_with_explicit_city_keeps_run_route(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(
            [
                "nl",
                "请你下载景德镇的数据，并分析最适合建设商场的前5个地址，输出报告",
            ]
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = args.func(args)
        self.assertEqual(rc, 0)
        raw = buf.getvalue().strip()
        payload = json.loads(raw.split("\n[NL]")[0].strip())
        self.assertEqual(payload["intent"], "run")
        self.assertEqual(payload["cli_args"][0], "run")
        self.assertIn("--city", payload["cli_args"])
        self.assertIn("景德镇市", payload["cli_args"])

    def test_mall_query_with_explicit_city_keeps_run_route_even_with_sre(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(
            [
                "nl",
                "请你下载景德镇的数据，并分析最适合建设商场的前5个地址，输出报告",
                "--use-sre",
            ]
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = args.func(args)
        self.assertEqual(rc, 0)
        raw = buf.getvalue().strip()
        payload = json.loads(raw.split("\n[NL]")[0].strip())
        self.assertEqual(payload["cli_args"][0], "run")
        self.assertIn("景德镇市", payload["cli_args"])
        notes = payload.get("tool_route_notes") or []
        self.assertTrue(any("keep native run route" in x.lower() for x in notes))

    def test_chat_session_persisted_non_interactive(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["GEOCLAW_OPENAI_HOME"] = os.path.join(tmp, "home")
                ensure_profile_layers()
                cli_main._SESSION_PROFILE = None

                args = argparse.Namespace(
                    message=["第一轮问题"],
                    message_opt="",
                    with_ai=False,
                    no_ai=True,
                    execute=False,
                    use_sre=False,
                    sre_report_out="",
                    interactive=False,
                    session_id="demo_session",
                    new_session=True,
                    max_history_turns=8,
                )
                buf_a = io.StringIO()
                with redirect_stdout(buf_a):
                    rc_a = cli_main.cmd_chat(args)
                self.assertEqual(rc_a, 0)
                payload_a = json.loads(buf_a.getvalue())
                self.assertIn("session", payload_a)
                self.assertEqual(payload_a["session"]["session_id"], "demo_session")
                self.assertEqual(payload_a["session"]["turns"], 1)
                self.assertIn("chat_memory", payload_a)
                self.assertEqual(payload_a["chat_memory"]["session_id"], "demo_session")

                args.message = ["第二轮问题"]
                args.new_session = False
                buf_b = io.StringIO()
                with redirect_stdout(buf_b):
                    rc_b = cli_main.cmd_chat(args)
                self.assertEqual(rc_b, 0)
                payload_b = json.loads(buf_b.getvalue())
                self.assertEqual(payload_b["session"]["session_id"], "demo_session")
                self.assertEqual(payload_b["session"]["turns"], 2)

                session_path = Path(payload_b["session"]["path"])
                self.assertTrue(session_path.exists())
                stored = json.loads(session_path.read_text(encoding="utf-8"))
                self.assertEqual(len(stored.get("turns", [])), 2)

                store = TaskMemoryStore()
                digest = store.get_chat_daily_digest(session_id="demo_session")
                self.assertEqual(int(digest.get("turn_count", 0)), 2)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            cli_main._SESSION_PROFILE = None

    def test_chat_interactive_mode_with_initial_message(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["GEOCLAW_OPENAI_HOME"] = os.path.join(tmp, "home")
                ensure_profile_layers()
                cli_main._SESSION_PROFILE = None

                args = argparse.Namespace(
                    message=["你好"],
                    message_opt="",
                    with_ai=False,
                    no_ai=True,
                    execute=False,
                    use_sre=False,
                    sre_report_out="",
                    interactive=True,
                    session_id="interactive_demo",
                    new_session=True,
                    max_history_turns=8,
                )
                buf = io.StringIO()
                with patch("builtins.input", side_effect=["退出"]), redirect_stdout(buf):
                    rc = cli_main.cmd_chat(args)
                self.assertEqual(rc, 0)
                raw = buf.getvalue()
                self.assertIn("GeoClaw>", raw)
                self.assertIn('"interactive": true', raw)
                self.assertIn('"session_id": "interactive_demo"', raw)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            cli_main._SESSION_PROFILE = None


if __name__ == "__main__":
    unittest.main()
