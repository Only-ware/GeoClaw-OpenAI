from __future__ import annotations

import json
import unittest
from dataclasses import dataclass
from typing import Any

from geoclaw_qgis.reasoning.input_adapter import build_reasoning_input
from geoclaw_qgis.reasoning.llm_reasoner import GeoMethodReasoner, ReasonerRuntimeConfig
from geoclaw_qgis.reasoning.rule_engine import run_rule_engine


@dataclass
class _FakeConfig:
    provider: str = "openai"
    model: str = "gpt-5-mini"


class _FakeClient:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.config = _FakeConfig()

    def chat(self, user_prompt: str, system_prompt: str = "") -> str:
        self.calls += 1
        if not self.responses:
            return "{}"
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return str(item)


def _build_input_and_rules(query: str = "计算站点周边500米范围内POI数量") -> tuple[Any, dict[str, Any]]:
    input_data = build_reasoning_input(
        query=query,
        datasets=[
            {"id": "stations", "type": "vector", "geometry": "point", "crs": "EPSG:4326"},
            {"id": "poi", "type": "vector", "geometry": "point", "crs": "EPSG:4326"},
        ],
        planner_hints={"candidate_task_type": "proximity_analysis"},
    )
    rule_package = run_rule_engine(input_data, task_candidates=["proximity_analysis"], primitives={})
    return input_data, rule_package


class TestReasoningLLMReasoner(unittest.TestCase):
    def test_deterministic_mode(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        reasoner = GeoMethodReasoner(runtime_config=ReasonerRuntimeConfig(mode="deterministic"))
        payload = reasoner.infer(input_data=input_data, rule_package=rule_package)
        self.assertEqual(payload["reasoner_backend"], "deterministic")
        self.assertIn("uncertainty_score", payload)
        self.assertIn(payload["uncertainty_level"], {"low", "medium", "high"})

    def test_external_mode_success(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        fake = _FakeClient(
            [
                json.dumps(
                    {
                        "inferred_goal": "buffer poi count",
                        "reasoning_mode": "exploratory",
                        "recommended_analysis_strategy": {
                            "primary_method": "buffer",
                            "secondary_methods": ["distance_to_nearest"],
                        },
                        "reasoning": ["use buffer first"],
                        "assumptions": ["poi is proxy"],
                        "limitations": ["radius sensitive"],
                        "sensitivity_hints": ["buffer_radius_sensitivity"],
                        "uncertainty_factors": ["sample_bias"],
                        "uncertainty_level": "medium",
                        "uncertainty_score": 0.52,
                    },
                    ensure_ascii=False,
                )
            ]
        )
        reasoner = GeoMethodReasoner(
            runtime_config=ReasonerRuntimeConfig(mode="external", max_retries=2, strict_external=True),
            ai_client=fake,
        )
        payload = reasoner.infer(input_data=input_data, rule_package=rule_package)
        self.assertEqual(payload["reasoner_backend"], "external_ai")
        self.assertEqual(payload["reasoner_attempts"], 1)
        self.assertEqual(payload["recommended_analysis_strategy"]["primary_method"], "buffer")
        self.assertEqual(payload["provider_model"], "openai:gpt-5-mini")

    def test_external_mode_retry_then_success(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        fake = _FakeClient(
            [
                "not-json",
                """```json
{"recommended_analysis_strategy":{"primary_method":"buffer","secondary_methods":["distance_to_nearest"]},
 "reasoning_mode":"exploratory",
 "reasoning":["retry success"],
 "assumptions":["ok"],
 "limitations":["ok"],
 "uncertainty_level":"medium",
 "uncertainty_score":0.4}
```""",
            ]
        )
        reasoner = GeoMethodReasoner(
            runtime_config=ReasonerRuntimeConfig(mode="external", max_retries=3, strict_external=False),
            ai_client=fake,
        )
        payload = reasoner.infer(input_data=input_data, rule_package=rule_package)
        self.assertEqual(payload["reasoner_backend"], "external_ai")
        self.assertEqual(payload["reasoner_attempts"], 2)
        self.assertEqual(fake.calls, 2)

    def test_external_mode_schema_retry_then_success(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        fake = _FakeClient(
            [
                json.dumps(
                    {
                        "recommended_analysis_strategy": {
                            "primary_method": "buffer",
                            "secondary_methods": ["distance_to_nearest"],
                        },
                        "reasoning_mode": "exploratory",
                        "reasoning": ["missing score on purpose"],
                        "assumptions": ["ok"],
                        "limitations": ["ok"],
                        "uncertainty_level": "medium",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "recommended_analysis_strategy": {
                            "primary_method": "buffer",
                            "secondary_methods": ["distance_to_nearest"],
                        },
                        "reasoning_mode": "exploratory",
                        "reasoning": ["schema fixed"],
                        "assumptions": ["ok"],
                        "limitations": ["ok"],
                        "uncertainty_level": "medium",
                        "uncertainty_score": 0.5,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        reasoner = GeoMethodReasoner(
            runtime_config=ReasonerRuntimeConfig(mode="external", max_retries=3, strict_external=False),
            ai_client=fake,
        )
        payload = reasoner.infer(input_data=input_data, rule_package=rule_package)
        self.assertEqual(payload["reasoner_backend"], "external_ai")
        self.assertEqual(payload["reasoner_attempts"], 2)
        self.assertEqual(fake.calls, 2)

    def test_external_mode_schema_retry_for_invalid_reasoning_shape(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        fake = _FakeClient(
            [
                json.dumps(
                    {
                        "recommended_analysis_strategy": {
                            "primary_method": "buffer",
                            "secondary_methods": ["distance_to_nearest"],
                        },
                        "reasoning_mode": "exploratory",
                        "reasoning": "must be list",
                        "assumptions": ["ok"],
                        "limitations": ["ok"],
                        "uncertainty_level": "medium",
                        "uncertainty_score": 0.5,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "recommended_analysis_strategy": {
                            "primary_method": "buffer",
                            "secondary_methods": ["distance_to_nearest"],
                        },
                        "reasoning_mode": "exploratory",
                        "reasoning": ["schema fixed"],
                        "assumptions": ["ok"],
                        "limitations": ["ok"],
                        "uncertainty_level": "medium",
                        "uncertainty_score": 0.5,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        reasoner = GeoMethodReasoner(
            runtime_config=ReasonerRuntimeConfig(mode="external", max_retries=3, strict_external=False),
            ai_client=fake,
        )
        payload = reasoner.infer(input_data=input_data, rule_package=rule_package)
        self.assertEqual(payload["reasoner_backend"], "external_ai")
        self.assertEqual(payload["reasoner_attempts"], 2)
        self.assertEqual(fake.calls, 2)

    def test_external_mode_fallback_when_non_strict(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        fake = _FakeClient(["bad-1", "bad-2"])
        reasoner = GeoMethodReasoner(
            runtime_config=ReasonerRuntimeConfig(mode="external", max_retries=2, strict_external=False),
            ai_client=fake,
        )
        payload = reasoner.infer(input_data=input_data, rule_package=rule_package)
        self.assertEqual(payload["reasoner_backend"], "deterministic_fallback")
        self.assertTrue(any("fallback deterministic" in x for x in payload["limitations"]))

    def test_external_error_detail_is_sanitized(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        fake = _FakeClient(
            [
                RuntimeError(
                    "AI API HTTP error: 401 Incorrect API key provided: test-key********-run "
                    "Incorrect API key provided: sk-secret-token-123456 "
                    "Authorization: Bearer sk-secret-token-123456"
                )
            ]
        )
        reasoner = GeoMethodReasoner(
            runtime_config=ReasonerRuntimeConfig(mode="external", max_retries=1, strict_external=False),
            ai_client=fake,
        )
        payload = reasoner.infer(input_data=input_data, rule_package=rule_package)
        limitations = "\n".join(payload.get("limitations") or [])
        self.assertIn("[REDACTED]", limitations)
        self.assertNotIn("sk-secret-token", limitations)
        self.assertNotIn("test-key********-run", limitations)
        self.assertNotIn("Bearer sk-", limitations)

    def test_external_mode_raises_when_strict(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        fake = _FakeClient(["bad-1", "bad-2"])
        reasoner = GeoMethodReasoner(
            runtime_config=ReasonerRuntimeConfig(mode="external", max_retries=2, strict_external=True),
            ai_client=fake,
        )
        with self.assertRaises(RuntimeError):
            reasoner.infer(input_data=input_data, rule_package=rule_package)

    def test_external_mode_strict_raise_is_sanitized(self) -> None:
        input_data, rule_package = _build_input_and_rules()
        fake = _FakeClient([RuntimeError("bad key sk-secret-token-654321")])
        reasoner = GeoMethodReasoner(
            runtime_config=ReasonerRuntimeConfig(mode="external", max_retries=1, strict_external=True),
            ai_client=fake,
        )
        with self.assertRaises(RuntimeError) as ctx:
            reasoner.infer(input_data=input_data, rule_package=rule_package)
        self.assertIn("[REDACTED]", str(ctx.exception))
        self.assertNotIn("sk-secret-token", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
