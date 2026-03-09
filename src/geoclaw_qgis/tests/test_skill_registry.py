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

    def test_vector_raster_network_skills_registered(self) -> None:
        root = Path(__file__).resolve().parents[3]
        registry = SkillRegistry(root / "configs" / "skills_registry.json")

        vector_skill = registry.get("vector_basics_qgis")
        self.assertEqual(vector_skill.skill_type, "pipeline")
        self.assertTrue(vector_skill.pipeline.endswith("pipelines/examples/vector_basics.yaml"))

        raster_skill = registry.get("raster_basics_qgis")
        self.assertEqual(raster_skill.skill_type, "pipeline")
        self.assertTrue(raster_skill.pipeline.endswith("pipelines/examples/raster_basics.yaml"))

        network_skill = registry.get("network_trackintel_skill")
        self.assertEqual(network_skill.skill_type, "builtin")
        self.assertEqual(network_skill.builtin, ["network"])

        operator_skill = registry.get("qgis_operator_skill")
        self.assertEqual(operator_skill.skill_type, "builtin")
        self.assertEqual(operator_skill.builtin, ["operator"])


if __name__ == "__main__":
    unittest.main()
