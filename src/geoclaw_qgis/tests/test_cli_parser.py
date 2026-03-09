from __future__ import annotations

import unittest

from geoclaw_qgis.cli.main import (
    _apply_sre_execution_plan,
    _apply_sre_task_route,
    _is_sre_route_compatible,
    _validate_sre_command_shape,
    build_parser,
)


class TestCLIParser(unittest.TestCase):
    def test_reasoning_command_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["reasoning", "测试任务"])
        self.assertEqual(args.command, "reasoning")
        self.assertEqual(args.query, ["测试任务"])

    def test_profile_evolve_command_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "profile",
                "evolve",
                "--target",
                "both",
                "--allow-soul",
                "--summary",
                "同步长期偏好",
                "--set",
                "preferred_language=Chinese",
                "--add",
                "preferred_tools=QGIS,Ollama",
            ]
        )
        self.assertEqual(args.command, "profile")
        self.assertEqual(args.profile_cmd, "evolve")
        self.assertEqual(args.target, "both")
        self.assertTrue(args.allow_soul)
        self.assertEqual(args.summary, "同步长期偏好")
        self.assertIn("preferred_language=Chinese", args.set_items)
        self.assertIn("preferred_tools=QGIS,Ollama", args.add_items)

    def test_chat_command_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["chat", "--message", "你好"])
        self.assertEqual(args.command, "chat")
        self.assertEqual(args.message_opt, "你好")

    def test_local_command_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["local", "--cmd", "ls -la", "--timeout", "10"])
        self.assertEqual(args.command, "local")
        self.assertEqual(args.cmd, "ls -la")
        self.assertEqual(args.timeout, 10)

    def test_nl_sre_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "nl",
                "商场选址分析",
                "--use-sre",
                "--sre-strict",
                "--sre-reasoner-mode",
                "external",
                "--sre-llm-retries",
                "3",
                "--sre-strict-external",
                "--sre-report-out",
                "data/outputs/reasoning/nl_report.md",
                "--sre-print-report",
            ]
        )
        self.assertEqual(args.command, "nl")
        self.assertTrue(args.use_sre)
        self.assertTrue(args.sre_strict)
        self.assertEqual(args.sre_reasoner_mode, "external")
        self.assertEqual(args.sre_llm_retries, 3)
        self.assertTrue(args.sre_strict_external)
        self.assertEqual(args.sre_report_out, "data/outputs/reasoning/nl_report.md")
        self.assertTrue(args.sre_print_report)

    def test_reasoning_report_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "reasoning",
                "测试任务",
                "--reasoner-mode",
                "auto",
                "--llm-retries",
                "2",
                "--strict-external",
                "--report-out",
                "data/outputs/reasoning/test_report.md",
                "--print-report",
            ]
        )
        self.assertEqual(args.command, "reasoning")
        self.assertEqual(args.reasoner_mode, "auto")
        self.assertEqual(args.llm_retries, 2)
        self.assertTrue(args.strict_external)
        self.assertEqual(args.report_out, "data/outputs/reasoning/test_report.md")
        self.assertTrue(args.print_report)

    def test_apply_sre_execution_plan_safe(self) -> None:
        base = ["run", "--case", "native_cases"]
        notes: list[str] = []
        routed, applied = _apply_sre_execution_plan(
            base,
            sre_payload={
                "execution_plan": {
                    "safe_to_execute": True,
                    "route_target": "skill",
                    "command": ["skill", "--", "--skill", "mall_site_selection_qgis", "--skip-download"],
                }
            },
            base_intent="run",
            route_notes=notes,
        )
        self.assertTrue(applied)
        self.assertEqual(routed[0], "skill")
        self.assertTrue(any("execution plan applied" in x for x in notes))

    def test_apply_sre_execution_plan_route_matrix(self) -> None:
        base = ["run", "--case", "native_cases"]
        allowed_plans = [
            ["run", "--case", "site_selection"],
            ["skill", "--", "--skill", "mall_site_selection_qgis"],
        ]
        for cmd in allowed_plans:
            with self.subTest(cmd=cmd):
                notes: list[str] = []
                routed, applied = _apply_sre_execution_plan(
                    base,
                    sre_payload={
                        "execution_plan": {
                            "safe_to_execute": True,
                            "route_target": cmd[0],
                            "command": cmd,
                        }
                    },
                    base_intent="run",
                    route_notes=notes,
                )
                self.assertTrue(applied)
                self.assertEqual(routed, cmd)
                self.assertTrue(any("execution plan applied" in x for x in notes))

        blocked_plans = [
            ["operator", "--algorithm", "native:buffer"],
            ["network", "--pfs-csv", "data/examples/trajectory/trackintel_demo_pfs.csv"],
        ]
        for cmd in blocked_plans:
            with self.subTest(cmd=cmd):
                notes = []
                routed, applied = _apply_sre_execution_plan(
                    base,
                    sre_payload={
                        "execution_plan": {
                            "safe_to_execute": True,
                            "route_target": cmd[0],
                            "command": cmd,
                        }
                    },
                    base_intent="run",
                    route_notes=notes,
                )
                self.assertFalse(applied)
                self.assertEqual(routed, base)
                self.assertTrue(any("cross-intent reroute" in x for x in notes))

    def test_apply_sre_execution_plan_blocked(self) -> None:
        base = ["run", "--case", "native_cases"]
        notes: list[str] = []
        routed, applied = _apply_sre_execution_plan(
            base,
            sre_payload={
                "execution_plan": {
                    "safe_to_execute": False,
                    "route_target": "blocked",
                    "command": [],
                    "blocking_reasons": ["TEMPORAL_SLICES_REQUIRED: need >=2 slices"],
                }
            },
            base_intent="run",
            route_notes=notes,
        )
        self.assertFalse(applied)
        self.assertEqual(routed, base)
        self.assertTrue(any("blocked" in x for x in notes))

    def test_apply_sre_execution_plan_rejects_unknown_command(self) -> None:
        base = ["run", "--case", "native_cases"]
        notes: list[str] = []
        routed, applied = _apply_sre_execution_plan(
            base,
            sre_payload={
                "execution_plan": {
                    "safe_to_execute": True,
                    "route_target": "external",
                    "command": ["rm", "-rf", "/"],
                }
            },
            base_intent="run",
            route_notes=notes,
        )
        self.assertFalse(applied)
        self.assertEqual(routed, base)
        self.assertTrue(any("unsupported root command" in x for x in notes))

    def test_validate_sre_command_shape_matrix(self) -> None:
        self.assertEqual(_validate_sre_command_shape(["run", "--case", "site_selection"])[0], True)
        self.assertEqual(_validate_sre_command_shape(["operator", "--algorithm", "native:buffer"])[0], True)
        self.assertEqual(_validate_sre_command_shape(["network", "--pfs-csv", "a.csv"])[0], True)
        self.assertEqual(_validate_sre_command_shape(["skill", "--", "--skill", "mall_site_selection_qgis"])[0], True)

        self.assertEqual(_validate_sre_command_shape(["run", "--case", "bad_case"])[0], False)
        self.assertEqual(_validate_sre_command_shape(["run"])[0], False)
        self.assertEqual(_validate_sre_command_shape(["operator"])[0], False)
        self.assertEqual(_validate_sre_command_shape(["network"])[0], False)
        self.assertEqual(_validate_sre_command_shape(["skill", "--"])[0], False)

    def test_apply_sre_execution_plan_rejects_invalid_shape(self) -> None:
        base = ["run", "--case", "native_cases"]
        notes: list[str] = []
        routed, applied = _apply_sre_execution_plan(
            base,
            sre_payload={
                "execution_plan": {
                    "safe_to_execute": True,
                    "route_target": "run",
                    "command": ["run", "--case", "unknown_case"],
                }
            },
            base_intent="run",
            route_notes=notes,
        )
        self.assertFalse(applied)
        self.assertEqual(routed, base)
        self.assertTrue(any("invalid command shape" in x for x in notes))

    def test_sre_rejected_then_fallback_to_task_route(self) -> None:
        base = ["run", "--case", "native_cases"]
        notes: list[str] = []
        routed, applied = _apply_sre_execution_plan(
            base,
            sre_payload={
                "execution_plan": {
                    "safe_to_execute": True,
                    "route_target": "run",
                    "command": ["run", "--case", "bad_case"],
                }
            },
            base_intent="run",
            route_notes=notes,
        )
        self.assertFalse(applied)
        fallback = _apply_sre_task_route(routed, "site_selection", notes)
        self.assertEqual(fallback, ["run", "--case", "site_selection"])
        self.assertTrue(any("invalid command shape" in x for x in notes))
        self.assertTrue(any("remapped run case" in x for x in notes))

    def test_route_compatibility_policy(self) -> None:
        self.assertTrue(_is_sre_route_compatible(base_intent="run", new_root="run"))
        self.assertTrue(_is_sre_route_compatible(base_intent="run", new_root="skill"))
        self.assertFalse(_is_sre_route_compatible(base_intent="run", new_root="network"))
        self.assertFalse(_is_sre_route_compatible(base_intent="run", new_root="operator"))
        self.assertTrue(_is_sre_route_compatible(base_intent="operator", new_root="operator"))
        self.assertFalse(_is_sre_route_compatible(base_intent="operator", new_root="run"))
        self.assertFalse(_is_sre_route_compatible(base_intent="network", new_root="run"))
        self.assertFalse(_is_sre_route_compatible(base_intent="skill", new_root="run"))

    def test_apply_sre_execution_plan_rejects_cross_intent_reroute(self) -> None:
        base = ["operator", "--algorithm", "native:buffer"]
        notes: list[str] = []
        routed, applied = _apply_sre_execution_plan(
            base,
            sre_payload={
                "execution_plan": {
                    "safe_to_execute": True,
                    "route_target": "run",
                    "command": ["run", "--case", "location_analysis"],
                }
            },
            base_intent="operator",
            route_notes=notes,
        )
        self.assertFalse(applied)
        self.assertEqual(routed, base)
        self.assertTrue(any("cross-intent reroute" in x for x in notes))


if __name__ == "__main__":
    unittest.main()
