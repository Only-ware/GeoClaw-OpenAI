from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from geoclaw_qgis.skills.openclaw_adapter import load_openclaw_skill_spec


class TestOpenClawAdapter(unittest.TestCase):
    def test_import_pipeline_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_file = root / "openclaw_pipeline.yaml"
            spec_file.write_text(
                "\n".join(
                    [
                        "id: location_score",
                        "type: workflow",
                        "description: city location analysis",
                        "workflow: pipelines/cases/location_analysis.yaml",
                        "report_path: data/outputs/location_score/pipeline_report.json",
                    ]
                ),
                encoding="utf-8",
            )
            converted = load_openclaw_skill_spec(spec_file, id_prefix="oc_")
            self.assertEqual(converted["id"], "oc_location_score")
            self.assertEqual(converted["type"], "pipeline")
            self.assertEqual(converted["pipeline"], "pipelines/cases/location_analysis.yaml")
            self.assertTrue(str(converted["report_path"]).startswith("data/outputs/"))

    def test_import_command_to_builtin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_file = root / "openclaw_cmd.json"
            spec_file.write_text(
                json.dumps(
                    {
                        "name": "buffer_skill",
                        "kind": "command",
                        "description": "buffer op",
                        "command": "geoclaw-openai operator --algorithm native:buffer --params-file configs/examples/operator_buffer_params.yaml",
                    }
                ),
                encoding="utf-8",
            )
            converted = load_openclaw_skill_spec(spec_file, id_prefix="oc_")
            self.assertEqual(converted["id"], "oc_buffer_skill")
            self.assertEqual(converted["type"], "builtin")
            self.assertEqual(converted["builtin"], ["operator"])
            self.assertIn("--algorithm", converted.get("default_args", []))

    def test_import_command_with_invalid_root_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spec_file = root / "bad_openclaw_cmd.json"
            spec_file.write_text(
                json.dumps(
                    {
                        "id": "bad_skill",
                        "type": "command",
                        "command": "geoclaw-openai local --cmd 'rm -rf /'",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_openclaw_skill_spec(spec_file)


if __name__ == "__main__":
    unittest.main()

