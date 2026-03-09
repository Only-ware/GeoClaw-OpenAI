from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from geoclaw_qgis.cli.main import cmd_reasoning
from geoclaw_qgis.reasoning import build_reasoning_input, run_spatial_reasoning
from geoclaw_qgis.reasoning.report_generator import render_reasoning_report


def _extract_json_payload(text: str) -> dict[str, object]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("json payload not found")
    return json.loads(text[start : end + 1])


class TestReasoningReport(unittest.TestCase):
    def test_render_reasoning_report_contains_milestone_d_fields(self) -> None:
        input_data = build_reasoning_input(
            query="分析地铁开通是否导致周边房价上涨，做因果推断",
            datasets=[{"id": "metro", "type": "vector", "geometry": "point", "crs": "EPSG:4326"}],
            planner_hints={"candidate_task_type": "spatial_comparison"},
        )
        result = run_spatial_reasoning(input_data)
        md = render_reasoning_report(input_data=input_data, result=result)
        self.assertIn("Reasoning Mode", md)
        self.assertIn("Uncertainty", md)
        self.assertIn("Sensitivity Hints", md)
        self.assertIn("Validation", md)
        self.assertIn("CAUSAL_GUARDRAIL_REQUIRED", md)

    @patch("geoclaw_qgis.cli.main.bootstrap_runtime_env")
    @patch("geoclaw_qgis.cli.main.get_session_profile")
    @patch("geoclaw_qgis.cli.main.resolve_workspace_root")
    @patch("geoclaw_qgis.cli.main.build_reasoning_input_from_profile")
    @patch("geoclaw_qgis.cli.main.run_spatial_reasoning")
    def test_cmd_reasoning_writes_report_under_outputs(
        self,
        mock_run_sre,
        mock_build_input,
        mock_workspace,
        mock_session,
        _mock_bootstrap,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/outputs/reasoning").mkdir(parents=True, exist_ok=True)

            input_data = build_reasoning_input(
                query="比较不同尺度单元下商业分布差异，注意MAUP影响",
                datasets=[{"id": "a", "type": "vector", "geometry": "polygon", "crs": "EPSG:4547"}],
                planner_hints={"candidate_task_type": "spatial_comparison"},
            )
            result = run_spatial_reasoning(input_data)

            mock_build_input.return_value = input_data
            mock_run_sre.return_value = result
            mock_workspace.return_value = root
            mock_session.return_value = type("S", (), {"soul_path": "soul.md", "user_path": "user.md"})()

            out_rel = "data/outputs/reasoning/test_reasoning_report.md"
            args = argparse.Namespace(
                query=["比较不同尺度单元下商业分布差异，注意MAUP影响"],
                datasets_file="",
                data_dir="",
                planner_task="spatial_comparison",
                planner_method=[],
                project_study_area="",
                project_crs="",
                project_goal="",
                report_out=out_rel,
                print_report=False,
                strict=False,
            )
            with io.StringIO() as buf, redirect_stdout(buf):
                rc = cmd_reasoning(args)
                out = buf.getvalue()

            self.assertEqual(rc, 0)
            payload = _extract_json_payload(out)
            self.assertIn("report", payload)
            report_path = root / out_rel
            self.assertTrue(report_path.exists())
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("GeoClaw Spatial Reasoning Report", content)

    @patch("geoclaw_qgis.cli.main.bootstrap_runtime_env")
    @patch("geoclaw_qgis.cli.main.get_session_profile")
    @patch("geoclaw_qgis.cli.main.resolve_workspace_root")
    @patch("geoclaw_qgis.cli.main.build_reasoning_input_from_profile")
    @patch("geoclaw_qgis.cli.main.run_spatial_reasoning")
    def test_cmd_reasoning_rejects_unsafe_report_path(
        self,
        mock_run_sre,
        mock_build_input,
        mock_workspace,
        mock_session,
        _mock_bootstrap,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/outputs").mkdir(parents=True, exist_ok=True)

            input_data = build_reasoning_input(
                query="测试",
                datasets=[],
                planner_hints={"candidate_task_type": "spatial_comparison"},
            )
            result = run_spatial_reasoning(input_data)
            mock_build_input.return_value = input_data
            mock_run_sre.return_value = result
            mock_workspace.return_value = root
            mock_session.return_value = type("S", (), {"soul_path": "soul.md", "user_path": "user.md"})()

            args = argparse.Namespace(
                query=["测试"],
                datasets_file="",
                data_dir="",
                planner_task="spatial_comparison",
                planner_method=[],
                project_study_area="",
                project_crs="",
                project_goal="",
                report_out="../unsafe.md",
                print_report=False,
                strict=False,
            )
            with self.assertRaises(RuntimeError):
                cmd_reasoning(args)


if __name__ == "__main__":
    unittest.main()
