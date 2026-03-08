from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import Mock, patch

from geoclaw_qgis.cli.main import cmd_nl
from geoclaw_qgis.nl.intent import NLPlan
from geoclaw_qgis.reasoning import build_reasoning_input, run_spatial_reasoning


@dataclass
class _FakeValidation:
    status: str = "pass"
    required_preconditions: list[str] = field(default_factory=list)
    revisions_applied: list[str] = field(default_factory=list)


@dataclass
class _FakeTaskProfile:
    task_type: str = "spatial_comparison"


class _FakeSRE:
    def __init__(self, payload: dict[str, object], *, status: str = "pass", task_type: str = "spatial_comparison") -> None:
        self._payload = payload
        self.validation = _FakeValidation(status=status)
        self.task_profile = _FakeTaskProfile(task_type=task_type)

    def to_dict(self) -> dict[str, object]:
        return dict(self._payload)


def _extract_payload(text: str) -> dict[str, object]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("JSON payload not found in output")
    return json.loads(text[start : end + 1])


class TestNLSRERouting(unittest.TestCase):
    @patch("geoclaw_qgis.cli.main.bootstrap_runtime_env")
    @patch("geoclaw_qgis.cli.main.get_session_profile")
    @patch("geoclaw_qgis.cli.main.parse_nl_query")
    @patch("geoclaw_qgis.cli.main.run_spatial_reasoning")
    @patch("geoclaw_qgis.cli.main.build_reasoning_input_from_profile")
    @patch("geoclaw_qgis.cli.main._collect_reasoning_datasets")
    def test_non_spatial_intent_skips_sre(
        self,
        mock_collect: Mock,
        mock_build_input: Mock,
        mock_run_sre: Mock,
        mock_parse: Mock,
        mock_session: Mock,
        _mock_bootstrap: Mock,
    ) -> None:
        mock_parse.return_value = NLPlan(
            query="查看长期memory",
            intent="memory",
            confidence=0.95,
            reasons=["memory"],
            cli_args=["memory", "long"],
        )
        mock_session.return_value = type("S", (), {"soul_path": "soul.md", "user_path": "user.md"})()

        args = argparse.Namespace(
            query=["查看长期memory"],
            use_sre=True,
            sre_strict=False,
            sre_data_dir="",
            sre_datasets_file="",
            execute=False,
        )
        with io.StringIO() as buf, redirect_stdout(buf):
            rc = cmd_nl(args)
            out = buf.getvalue()

        self.assertEqual(rc, 0)
        payload = _extract_payload(out)
        self.assertEqual(payload["intent"], "memory")
        self.assertIsNone(payload["sre"])
        self.assertTrue(any("skipped for non-spatial intent" in x for x in payload["tool_route_notes"]))
        mock_collect.assert_not_called()
        mock_build_input.assert_not_called()
        mock_run_sre.assert_not_called()

    @patch("geoclaw_qgis.cli.main.bootstrap_runtime_env")
    @patch("geoclaw_qgis.cli.main.get_session_profile")
    @patch("geoclaw_qgis.cli.main.parse_nl_query")
    @patch("geoclaw_qgis.cli.main.run_spatial_reasoning")
    @patch("geoclaw_qgis.cli.main.build_reasoning_input_from_profile")
    @patch("geoclaw_qgis.cli.main._collect_reasoning_datasets")
    def test_cross_intent_reroute_is_rejected(
        self,
        mock_collect: Mock,
        mock_build_input: Mock,
        mock_run_sre: Mock,
        mock_parse: Mock,
        mock_session: Mock,
        _mock_bootstrap: Mock,
    ) -> None:
        mock_collect.return_value = []
        mock_build_input.return_value = object()
        mock_parse.return_value = NLPlan(
            query="执行buffer缓冲",
            intent="operator",
            confidence=0.9,
            reasons=["operator"],
            cli_args=["operator", "--algorithm", "native:buffer"],
        )
        mock_session.return_value = type("S", (), {"soul_path": "soul.md", "user_path": "user.md"})()
        mock_run_sre.return_value = _FakeSRE(
            {
                "validation": {"status": "pass"},
                "execution_plan": {
                    "safe_to_execute": True,
                    "route_target": "run",
                    "command": ["run", "--case", "location_analysis"],
                },
            },
            status="pass",
            task_type="proximity_analysis",
        )

        args = argparse.Namespace(
            query=["执行buffer缓冲"],
            use_sre=True,
            sre_strict=False,
            sre_data_dir="",
            sre_datasets_file="",
            execute=False,
        )
        with io.StringIO() as buf, redirect_stdout(buf):
            rc = cmd_nl(args)
            out = buf.getvalue()

        self.assertEqual(rc, 0)
        payload = _extract_payload(out)
        self.assertEqual(payload["intent"], "operator")
        self.assertEqual(payload["cli_args"], ["operator", "--algorithm", "native:buffer"])
        self.assertTrue(any("cross-intent reroute" in x for x in payload["tool_route_notes"]))

    @patch("geoclaw_qgis.cli.main.bootstrap_runtime_env")
    @patch("geoclaw_qgis.cli.main.get_session_profile")
    @patch("geoclaw_qgis.cli.main.parse_nl_query")
    @patch("geoclaw_qgis.cli.main.run_spatial_reasoning")
    @patch("geoclaw_qgis.cli.main.build_reasoning_input_from_profile")
    @patch("geoclaw_qgis.cli.main._collect_reasoning_datasets")
    def test_same_intent_route_is_applied(
        self,
        mock_collect: Mock,
        mock_build_input: Mock,
        mock_run_sre: Mock,
        mock_parse: Mock,
        mock_session: Mock,
        _mock_bootstrap: Mock,
    ) -> None:
        mock_collect.return_value = []
        mock_build_input.return_value = object()
        mock_parse.return_value = NLPlan(
            query="请做复杂网络分析",
            intent="network",
            confidence=0.9,
            reasons=["network"],
            cli_args=["network", "--pfs-csv", "x.csv"],
        )
        mock_session.return_value = type("S", (), {"soul_path": "soul.md", "user_path": "user.md"})()
        mock_run_sre.return_value = _FakeSRE(
            {
                "validation": {"status": "pass"},
                "execution_plan": {
                    "safe_to_execute": True,
                    "route_target": "network",
                    "command": ["network", "--pfs-csv", "y.csv"],
                },
            },
            status="pass",
            task_type="trajectory_analysis",
        )

        args = argparse.Namespace(
            query=["请做复杂网络分析"],
            use_sre=True,
            sre_strict=False,
            sre_data_dir="",
            sre_datasets_file="",
            execute=False,
        )
        with io.StringIO() as buf, redirect_stdout(buf):
            rc = cmd_nl(args)
            out = buf.getvalue()

        self.assertEqual(rc, 0)
        payload = _extract_payload(out)
        self.assertEqual(payload["intent"], "network")
        self.assertEqual(payload["cli_args"], ["network", "--pfs-csv", "y.csv"])
        self.assertTrue(any("execution plan applied" in x for x in payload["tool_route_notes"]))

    @patch("geoclaw_qgis.cli.main.bootstrap_runtime_env")
    @patch("geoclaw_qgis.cli.main.get_session_profile")
    @patch("geoclaw_qgis.cli.main.parse_nl_query")
    @patch("geoclaw_qgis.cli.main.resolve_workspace_root")
    @patch("geoclaw_qgis.cli.main.run_spatial_reasoning")
    @patch("geoclaw_qgis.cli.main.build_reasoning_input_from_profile")
    @patch("geoclaw_qgis.cli.main._collect_reasoning_datasets")
    def test_nl_writes_sre_report_when_requested(
        self,
        mock_collect: Mock,
        mock_build_input: Mock,
        mock_run_sre: Mock,
        mock_workspace: Mock,
        mock_parse: Mock,
        mock_session: Mock,
        _mock_bootstrap: Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/outputs/reasoning").mkdir(parents=True, exist_ok=True)

            mock_collect.return_value = []
            mock_parse.return_value = NLPlan(
                query="商场选址分析",
                intent="run",
                confidence=0.9,
                reasons=["run"],
                cli_args=["run", "--case", "site_selection"],
            )
            mock_session.return_value = type("S", (), {"soul_path": "soul.md", "user_path": "user.md"})()
            mock_workspace.return_value = root

            input_data = build_reasoning_input(
                query="商场选址分析",
                datasets=[],
                planner_hints={"candidate_task_type": "site_selection"},
            )
            result = run_spatial_reasoning(input_data)
            mock_build_input.return_value = input_data
            mock_run_sre.return_value = result

            args = argparse.Namespace(
                query=["商场选址分析"],
                use_sre=True,
                sre_strict=False,
                sre_data_dir="",
                sre_datasets_file="",
                sre_reasoner_mode="deterministic",
                sre_llm_retries=0,
                sre_strict_external=False,
                sre_report_out="data/outputs/reasoning/nl_sre_report.md",
                sre_print_report=False,
                execute=False,
            )
            with io.StringIO() as buf, redirect_stdout(buf):
                rc = cmd_nl(args)
                out = buf.getvalue()

            self.assertEqual(rc, 0)
            payload = _extract_payload(out)
            self.assertIn("sre_report", payload)
            report_path = root / "data/outputs/reasoning/nl_sre_report.md"
            self.assertTrue(report_path.exists())
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("GeoClaw Spatial Reasoning Report", content)

    @patch("geoclaw_qgis.cli.main.bootstrap_runtime_env")
    @patch("geoclaw_qgis.cli.main.get_session_profile")
    @patch("geoclaw_qgis.cli.main.parse_nl_query")
    def test_nl_rejects_report_without_sre(
        self,
        mock_parse: Mock,
        mock_session: Mock,
        _mock_bootstrap: Mock,
    ) -> None:
        mock_parse.return_value = NLPlan(
            query="商场选址分析",
            intent="run",
            confidence=0.9,
            reasons=["run"],
            cli_args=["run", "--case", "site_selection"],
        )
        mock_session.return_value = type("S", (), {"soul_path": "soul.md", "user_path": "user.md"})()

        args = argparse.Namespace(
            query=["商场选址分析"],
            use_sre=False,
            sre_strict=False,
            sre_data_dir="",
            sre_datasets_file="",
            sre_reasoner_mode="",
            sre_llm_retries=0,
            sre_strict_external=False,
            sre_report_out="data/outputs/reasoning/nl_sre_report.md",
            sre_print_report=False,
            execute=False,
        )
        with self.assertRaises(RuntimeError):
            cmd_nl(args)


if __name__ == "__main__":
    unittest.main()
