from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geoclaw_qgis.reasoning.config_loader import (
    clear_sre_config_cache,
    load_method_templates,
    load_reasoner_template,
    load_rule_config,
)


class TestReasoningConfigLoader(unittest.TestCase):
    def setUp(self) -> None:
        clear_sre_config_cache()

    def tearDown(self) -> None:
        clear_sre_config_cache()

    def test_default_catalog_contains_core_tasks(self) -> None:
        templates = load_method_templates()
        self.assertIn("site_selection", templates)
        self.assertIn("proximity_analysis", templates)
        self.assertTrue(bool(templates["site_selection"]))

        rules = load_rule_config()
        self.assertIn("constraints", rules)
        self.assertIn("warnings", rules)
        self.assertIn("distance_requires_projected_crs", rules["constraints"])
        self.assertIn("causal", rules["keywords"])
        self.assertIn("exploratory", rules["keywords"])

        reasoner = load_reasoner_template()
        self.assertIn("system_prompt", reasoner)
        self.assertIn("output_schema", reasoner)
        self.assertIn("required", reasoner["output_schema"])

    def test_override_template_from_custom_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tdir = root / "templates"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "proximity.yaml").write_text(
                "task_type: proximity_analysis\nmethods:\n  - custom_buffer\n  - custom_summary\n",
                encoding="utf-8",
            )

            templates = load_method_templates(templates_dir=str(tdir))
            self.assertEqual(templates["proximity_analysis"][:2], ["custom_buffer", "custom_summary"])
            self.assertIn("site_selection", templates)

    def test_override_rules_from_custom_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rdir = root / "rules"
            rdir.mkdir(parents=True, exist_ok=True)
            (rdir / "crs_rules.yaml").write_text(
                "keywords:\n  distance:\n    - foo_distance\n",
                encoding="utf-8",
            )
            (rdir / "temporal_rules.yaml").write_text(
                "temporal_rules:\n  change_detection_min_slices: 3\n",
                encoding="utf-8",
            )

            rules = load_rule_config(rules_dir=str(rdir))
            self.assertEqual(rules["keywords"]["distance"], ["foo_distance"])
            self.assertEqual(rules["temporal_rules"]["change_detection_min_slices"], 3)
            self.assertIn("readonly_inputs", rules["constraints"])

    def test_strict_mode_rejects_invalid_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tdir = root / "templates"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "proximity.yaml").write_text(
                "task_type: proximity_analysis\nmethods: invalid\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_method_templates(templates_dir=str(tdir), strict=True)

    def test_strict_mode_rejects_invalid_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rdir = root / "rules"
            rdir.mkdir(parents=True, exist_ok=True)
            (rdir / "temporal_rules.yaml").write_text(
                "temporal_rules:\n  change_detection_min_slices: 0\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_rule_config(rules_dir=str(rdir), strict=True)

    def test_override_reasoner_template_from_custom_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tdir = root / "templates"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "llm_reasoner.yaml").write_text(
                "system_prompt: test-system\n"
                "user_instruction: test-user\n"
                "output_schema:\n"
                "  required: [recommended_analysis_strategy, reasoning_mode, reasoning, assumptions, limitations, uncertainty_level, uncertainty_score]\n"
                "  recommended_analysis_strategy_required: [primary_method, secondary_methods]\n"
                "  reasoning_mode_values: [exploratory, causal_inference]\n"
                "  uncertainty_level_values: [low, medium, high]\n"
                "  max_secondary_methods: 2\n",
                encoding="utf-8",
            )
            cfg = load_reasoner_template(templates_dir=str(tdir))
            self.assertEqual(cfg["system_prompt"], "test-system")
            self.assertEqual(cfg["output_schema"]["max_secondary_methods"], 2)

    def test_strict_mode_rejects_invalid_reasoner_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tdir = root / "templates"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "llm_reasoner.yaml").write_text(
                "system_prompt: x\nuser_instruction: y\noutput_schema:\n  required: invalid\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_reasoner_template(templates_dir=str(tdir), strict=True)

    def test_non_strict_invalid_reasoner_template_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tdir = root / "templates"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "llm_reasoner.yaml").write_text(
                "system_prompt: x\nuser_instruction: y\noutput_schema:\n  required: invalid\n",
                encoding="utf-8",
            )
            cfg = load_reasoner_template(templates_dir=str(tdir), strict=False)
            self.assertIn("required", cfg["output_schema"])
            self.assertIsInstance(cfg["output_schema"]["required"], list)
            self.assertGreater(len(cfg["output_schema"]["required"]), 0)


if __name__ == "__main__":
    unittest.main()
