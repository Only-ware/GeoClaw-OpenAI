from __future__ import annotations

import unittest
from pathlib import Path

from geoclaw_qgis.skills import SkillRegistry


class TestSkillRegistry(unittest.TestCase):
    def test_mall_site_selection_skills_registered(self) -> None:
        root = Path(__file__).resolve().parents[3]
        registry = SkillRegistry(root / "configs" / "skills_registry.json")

        qgis_skill = registry.get("mall_site_selection_qgis")
        self.assertEqual(qgis_skill.skill_type, "pipeline")
        self.assertTrue(qgis_skill.pipeline.endswith("mall_site_selection_qgis.yaml"))
        self.assertTrue(qgis_skill.report_path.endswith("data/outputs/mall_site_qgis/pipeline_report.json"))

        llm_skill = registry.get("mall_site_selection_llm")
        self.assertEqual(llm_skill.skill_type, "ai")
        self.assertIn("mall site selection", llm_skill.description.lower())
        self.assertTrue(bool(llm_skill.system_prompt.strip()))


if __name__ == "__main__":
    unittest.main()
