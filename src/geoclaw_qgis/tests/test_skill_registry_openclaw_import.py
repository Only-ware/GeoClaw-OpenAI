from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from geoclaw_qgis.cli.main import cmd_skill_registry_import_openclaw


class TestSkillRegistryImportOpenClaw(unittest.TestCase):
    @patch("geoclaw_qgis.cli.main.bootstrap_runtime_env")
    @patch("geoclaw_qgis.cli.main.resolve_workspace_root")
    def test_import_openclaw_dry_run(self, mock_root, mock_bootstrap) -> None:
        del mock_bootstrap
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mock_root.return_value = root
            (root / "scripts").mkdir(parents=True, exist_ok=True)

            spec_file = root / "oc_skill.yaml"
            spec_file.write_text(
                "\n".join(
                    [
                        "id: demo_run_skill",
                        "type: command",
                        "description: demo run",
                        "command: geoclaw-openai run --case location_analysis --skip-download",
                    ]
                ),
                encoding="utf-8",
            )

            args = argparse.Namespace(
                spec_file=str(spec_file),
                registry="configs/skills_registry.json",
                id_prefix="oc_",
                replace=False,
                allow_high_risk=False,
                confirm=False,
                dry_run=True,
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cmd_skill_registry_import_openclaw(args)
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("imported"))
            self.assertEqual(payload.get("source"), "openclaw")
            self.assertEqual(payload.get("registered"), False)
            self.assertTrue(payload.get("dry_run"))
            converted = payload.get("converted_spec") or {}
            self.assertEqual(converted.get("type"), "builtin")
            self.assertEqual(converted.get("builtin"), ["run"])


if __name__ == "__main__":
    unittest.main()

