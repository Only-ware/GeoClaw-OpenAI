from __future__ import annotations

import argparse
import importlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from geoclaw_qgis.profile import ensure_profile_layers


cli_main = importlib.import_module("geoclaw_qgis.cli.main")


class TestChatMode(unittest.TestCase):
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

    def test_local_command_execution(self) -> None:
        args = argparse.Namespace(cmd="echo geoclaw_local_ok", cwd="", timeout=10, shell=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main.cmd_local(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["return_code"], 0)
        self.assertIn("geoclaw_local_ok", payload["stdout"])


if __name__ == "__main__":
    unittest.main()
