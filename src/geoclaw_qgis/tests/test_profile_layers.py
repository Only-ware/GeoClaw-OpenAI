from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from geoclaw_qgis.nl import parse_nl_query
from geoclaw_qgis.profile import ensure_profile_layers, load_session_profile


class TestProfileLayers(unittest.TestCase):
    def test_profile_layers_load_and_parse(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                os.environ["GEOCLAW_OPENAI_HOME"] = str(root / "home")

                (root / "soul.md").write_text(
                    "\n".join(
                        [
                            "# Soul.md",
                            "## Mission",
                            "Serve reproducible geospatial workflows.",
                            "## Core Principles",
                            "- Always keep analysis reproducible.",
                            "## Execution Hierarchy",
                            "1. Registered GeoClaw skills",
                            "2. QGIS / qgis_process tools",
                        ]
                    ),
                    encoding="utf-8",
                )
                (root / "user.md").write_text(
                    "\n".join(
                        [
                            "# User.md",
                            "## Identity",
                            "Role: urban geographer",
                            "Domain: mobility analysis",
                            "## Language Preference",
                            "Preferred language: Chinese",
                            "## Tool Preferences",
                            "- QGIS",
                            "- GDAL / OGR",
                            "## Common Project Contexts",
                            "- site selection",
                        ]
                    ),
                    encoding="utf-8",
                )

                ensured = ensure_profile_layers(root)
                self.assertTrue(Path(ensured["home_soul"]).exists())
                self.assertTrue(Path(ensured["home_user"]).exists())

                session = load_session_profile(root, force_reload=True)
                self.assertEqual(session.user.role, "urban geographer")
                self.assertEqual(session.user.preferred_language, "Chinese")
                self.assertIn("Registered GeoClaw skills", session.soul.execution_hierarchy[0])
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_nl_plan_uses_profile_context(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                os.environ["GEOCLAW_OPENAI_HOME"] = str(root / "home")
                ensure_profile_layers(root)
                session = load_session_profile(root, force_reload=True)

                plan = parse_nl_query("skill 商场选址 ai", session=session)
                self.assertEqual(plan.intent, "skill")
                self.assertIn("mall_site_selection_llm", plan.cli_args)
                self.assertTrue(any("Execution hierarchy priority" in x for x in plan.reasons))
        finally:
            os.environ.clear()
            os.environ.update(old_env)


if __name__ == "__main__":
    unittest.main()
