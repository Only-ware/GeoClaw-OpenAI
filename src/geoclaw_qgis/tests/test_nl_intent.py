from __future__ import annotations

import unittest

from geoclaw_qgis.nl import parse_nl_query


class TestNLIntent(unittest.TestCase):
    def test_update_check_intent(self) -> None:
        plan = parse_nl_query("检查一下有没有更新")
        self.assertEqual(plan.intent, "update")
        self.assertEqual(plan.cli_args, ["update", "--check-only"])

    def test_update_intent_for_english_plural_updates(self) -> None:
        plan = parse_nl_query("check for updates")
        self.assertEqual(plan.intent, "update")
        self.assertEqual(plan.cli_args, ["update", "--check-only"])

    def test_memory_long_intent(self) -> None:
        plan = parse_nl_query("查看长期memory")
        self.assertEqual(plan.intent, "memory")
        self.assertEqual(plan.cli_args, ["memory", "long"])

    def test_run_site_selection_with_city(self) -> None:
        plan = parse_nl_query("用武汉市做选址分析，前20个，出图")
        self.assertEqual(plan.intent, "run")
        self.assertIn("--case", plan.cli_args)
        self.assertIn("site_selection", plan.cli_args)
        self.assertIn("--city", plan.cli_args)
        self.assertIn("武汉市", plan.cli_args)
        self.assertIn("--top-n", plan.cli_args)
        self.assertIn("20", plan.cli_args)
        self.assertIn("--with-maps", plan.cli_args)

    def test_run_location_with_bbox(self) -> None:
        plan = parse_nl_query("请按bbox 30.50,114.20,30.66,114.45 跑区位分析")
        self.assertEqual(plan.intent, "run")
        self.assertIn("location_analysis", plan.cli_args)
        self.assertIn("--bbox", plan.cli_args)
        self.assertIn("30.50,114.20,30.66,114.45", plan.cli_args)

    def test_operator_buffer(self) -> None:
        plan = parse_nl_query("执行buffer缓冲 1000m")
        self.assertEqual(plan.intent, "operator")
        self.assertIn("--algorithm", plan.cli_args)
        self.assertIn("native:buffer", plan.cli_args)
        self.assertIn("DISTANCE=1000", plan.cli_args)

    def test_network_trackintel_intent(self) -> None:
        plan = parse_nl_query("请做复杂网络分析，使用trackintel")
        self.assertEqual(plan.intent, "network")
        self.assertIn("network", plan.cli_args)
        self.assertIn("--pfs-csv", plan.cli_args)

    def test_profile_evolve_intent(self) -> None:
        plan = parse_nl_query("请根据这次对话更新user.md偏好，偏好中文并优先ollama")
        self.assertEqual(plan.intent, "profile")
        self.assertEqual(plan.cli_args[0:2], ["profile", "evolve"])
        self.assertIn("--target", plan.cli_args)
        self.assertIn("user", plan.cli_args)
        self.assertIn("--set", plan.cli_args)
        self.assertIn("preferred_language=Chinese", plan.cli_args)
        self.assertIn("--add", plan.cli_args)
        self.assertIn("preferred_tools=Ollama", plan.cli_args)

    def test_chat_intent_for_greeting(self) -> None:
        plan = parse_nl_query("你好，今天怎么样")
        self.assertEqual(plan.intent, "chat")
        self.assertEqual(plan.cli_args[0], "chat")
        self.assertIn("--message", plan.cli_args)

    def test_local_tool_intent(self) -> None:
        plan = parse_nl_query("执行命令: ls -la")
        self.assertEqual(plan.intent, "local")
        self.assertEqual(plan.cli_args[0], "local")
        self.assertIn("--cmd", plan.cli_args)
        self.assertIn("ls -la", plan.cli_args)

    def test_mall_request_not_routed_to_chat(self) -> None:
        plan = parse_nl_query("请你下载景德镇的数据，并分析最适合建设商场的前5个地址，输出报告")
        self.assertEqual(plan.intent, "run")
        self.assertIn("--city", plan.cli_args)
        self.assertIn("景德镇市", plan.cli_args)
        self.assertIn("site_selection", plan.cli_args)

    def test_generic_city_detection_for_any_city(self) -> None:
        plan = parse_nl_query("请在南京市做商场选址分析，前8个")
        self.assertEqual(plan.intent, "run")
        self.assertIn("--city", plan.cli_args)
        self.assertIn("南京市", plan.cli_args)
        self.assertIn("--top-n", plan.cli_args)
        self.assertIn("8", plan.cli_args)

    def test_no_hardcoded_city_fallback_when_source_missing(self) -> None:
        plan = parse_nl_query("做一个选址分析，给出前5个")
        self.assertEqual(plan.intent, "run")
        self.assertIn("site_selection", plan.cli_args)
        self.assertNotIn("武汉市", plan.cli_args)
        self.assertNotIn("--city", plan.cli_args)

    def test_chat_query_not_misrouted_to_network_by_substring(self) -> None:
        plan = parse_nl_query("Hi GeoClaw, can you briefly introduce yourself?")
        self.assertEqual(plan.intent, "chat")
        self.assertEqual(plan.cli_args[0], "chat")

    def test_summarize_previous_turn_not_treated_as_city(self) -> None:
        plan = parse_nl_query("Can you summarize what I asked in previous turn?")
        self.assertEqual(plan.intent, "chat")
        self.assertEqual(plan.cli_args[0], "chat")

    def test_intro_with_spatial_terms_stays_chat(self) -> None:
        plan = parse_nl_query("请记住GeoClaw-OpenAI是GIS/GeoAI空间分析智能体，不是Clawpack海啸GeoClaw，并一句话介绍你自己。")
        self.assertEqual(plan.intent, "chat")
        self.assertEqual(plan.cli_args[0], "chat")


if __name__ == "__main__":
    unittest.main()
