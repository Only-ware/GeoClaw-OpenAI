from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from geoclaw_qgis.cli.main import build_parser


class TestInstallOps(unittest.TestCase):
    def test_uninstall_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["uninstall", "--dry-run", "--yes"]) 
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = args.func(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload.get("command"), "uninstall")
        self.assertTrue(payload.get("dry_run"))
        self.assertIn("pip_command", payload)

    def test_reinstall_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["reinstall", "--dry-run", "--yes"]) 
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = args.func(args)
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload.get("command"), "reinstall")
        self.assertTrue(payload.get("dry_run"))
        self.assertIn("install_plan", payload)


if __name__ == "__main__":
    unittest.main()
