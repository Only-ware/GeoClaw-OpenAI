from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from geoclaw_qgis.ai import ExternalAIClient, ExternalAIConfig

from .config_loader import load_reasoner_template
from .schemas import ReasoningInput


def _to_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _score_uncertainty(*, factors: list[str], mode: str, dataset_count: int) -> float:
    score = 0.2 + 0.12 * len({x for x in factors if str(x).strip()})
    if mode == "causal_inference":
        score += 0.2
    if dataset_count >= 2 and not factors:
        score -= 0.1
    return _clamp01(max(0.05, min(0.95, score)))


def _to_uncertainty_level(score: float) -> str:
    if score <= 0.35:
        return "low"
    if score <= 0.7:
        return "medium"
    return "high"


def _extract_json_object(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty llm response")

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    if start < 0:
        raise ValueError("llm response does not contain JSON object")
    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1].strip()
    raise ValueError("failed to locate complete JSON object in llm response")


def _sanitize_error_detail(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return "unknown_error"
    patterns: list[tuple[str, str]] = [
        (r"sk-[A-Za-z0-9_\-]{6,}", "[REDACTED]"),
        (r"Bearer\s+[A-Za-z0-9._\-]{6,}", "Bearer [REDACTED]"),
        (r"(?i)(api[_\s-]?key\s*[:=]\s*)[A-Za-z0-9._\-]{6,}", r"\1[REDACTED]"),
        (r"(?i)(incorrect api key provided:\s*)[^,\s\"}]+", r"\1[REDACTED]"),
    ]
    out = text
    for pat, repl in patterns:
        out = re.sub(pat, repl, out)
    if len(out) > 320:
        out = out[:320].rstrip() + "...[truncated]"
    return out


def _validate_external_payload(payload: dict[str, Any], *, reasoner_template: dict[str, Any]) -> None:
    schema = reasoner_template.get("output_schema", {})
    if not isinstance(schema, dict):
        raise ValueError("reasoner template output_schema must be mapping")

    required_fields = _to_str_list(schema.get("required"))
    for field in required_fields:
        if field not in payload:
            raise ValueError(f"llm payload missing required field: {field}")

    strategy = payload.get("recommended_analysis_strategy")
    if not isinstance(strategy, dict):
        raise ValueError("recommended_analysis_strategy must be object")
    for field in _to_str_list(schema.get("recommended_analysis_strategy_required")):
        if field not in strategy:
            raise ValueError(f"recommended_analysis_strategy missing field: {field}")
    primary_method = str(strategy.get("primary_method", "")).strip()
    if not primary_method:
        raise ValueError("recommended_analysis_strategy.primary_method must be non-empty string")

    mode = str(payload.get("reasoning_mode", "")).strip()
    mode_values = set(_to_str_list(schema.get("reasoning_mode_values")))
    if mode_values and mode and mode not in mode_values:
        raise ValueError(f"reasoning_mode must be one of {sorted(mode_values)}")

    level = str(payload.get("uncertainty_level", "")).strip()
    level_values = set(_to_str_list(schema.get("uncertainty_level_values")))
    if level_values and level and level not in level_values:
        raise ValueError(f"uncertainty_level must be one of {sorted(level_values)}")

    try:
        score = float(payload.get("uncertainty_score", 0.0))
    except Exception as exc:
        raise ValueError("uncertainty_score must be number") from exc
    if not (0.0 <= score <= 1.0):
        raise ValueError("uncertainty_score must be between 0 and 1")

    secondary = strategy.get("secondary_methods")
    if secondary is not None and not isinstance(secondary, list):
        raise ValueError("secondary_methods must be list")
    if isinstance(secondary, list):
        for item in secondary:
            if not str(item).strip():
                raise ValueError("secondary_methods must contain non-empty values")
    max_secondary = int(schema.get("max_secondary_methods", 3) or 3)
    if isinstance(secondary, list) and len(secondary) > max_secondary:
        raise ValueError(f"secondary_methods exceeds max_secondary_methods={max_secondary}")

    for field in ("reasoning", "assumptions", "limitations"):
        value = payload.get(field)
        if not isinstance(value, list) or not value:
            raise ValueError(f"{field} must be a non-empty list")
        for item in value:
            if not str(item).strip():
                raise ValueError(f"{field} must contain non-empty values")


@dataclass(frozen=True)
class ReasonerRuntimeConfig:
    mode: str = "auto"  # auto | deterministic | external
    max_retries: int = 2
    strict_external: bool = False

    @classmethod
    def from_env(cls) -> ReasonerRuntimeConfig:
        mode = os.environ.get("GEOCLAW_SRE_REASONER_MODE", "auto").strip().lower() or "auto"
        if mode not in {"auto", "deterministic", "external"}:
            mode = "auto"
        try:
            retries = int(os.environ.get("GEOCLAW_SRE_LLM_MAX_RETRIES", "2").strip() or "2")
        except Exception:
            retries = 2
        retries = max(1, min(5, retries))
        strict_raw = os.environ.get("GEOCLAW_SRE_STRICT_EXTERNAL", "0").strip().lower()
        strict_external = strict_raw in {"1", "true", "yes", "on"}
        return cls(mode=mode, max_retries=retries, strict_external=strict_external)


class GeoMethodReasoner:
    """Reasoner with deterministic baseline + optional external LLM enhancement."""

    def __init__(
        self,
        *,
        runtime_config: ReasonerRuntimeConfig | None = None,
        ai_client: ExternalAIClient | None = None,
    ) -> None:
        self.runtime_config = runtime_config or ReasonerRuntimeConfig.from_env()
        self._ai_client = ai_client

    def infer(self, *, input_data: ReasoningInput, rule_package: dict[str, Any]) -> dict[str, Any]:
        deterministic = self._infer_deterministic(input_data=input_data, rule_package=rule_package)
        mode = self.runtime_config.mode
        if mode == "deterministic":
            out = dict(deterministic)
            out["reasoner_backend"] = "deterministic"
            return out

        client, init_error = self._resolve_client()
        if client is None:
            if mode == "external" and self.runtime_config.strict_external:
                raise RuntimeError(f"external reasoner init failed: {_sanitize_error_detail(init_error)}")
            return self._fallback(
                deterministic,
                note=f"External reasoner unavailable; fallback deterministic. detail={_sanitize_error_detail(init_error)}",
                backend="deterministic_fallback",
            )

        last_error = ""
        reasoner_template = load_reasoner_template()
        for idx in range(self.runtime_config.max_retries):
            try:
                system_prompt, user_prompt = self._build_external_prompts(
                    input_data=input_data,
                    rule_package=rule_package,
                    deterministic=deterministic,
                    reasoner_template=reasoner_template,
                )
                raw = client.chat(user_prompt=user_prompt, system_prompt=system_prompt)
                payload = json.loads(_extract_json_object(raw))
                if not isinstance(payload, dict):
                    raise ValueError("LLM JSON root must be object")
                _validate_external_payload(payload, reasoner_template=reasoner_template)
                merged = self._merge_external_payload(
                    deterministic=deterministic,
                    payload=payload,
                    input_data=input_data,
                    rule_package=rule_package,
                    client=client,
                    reasoner_template=reasoner_template,
                )
                merged["reasoner_backend"] = "external_ai"
                merged["reasoner_attempts"] = idx + 1
                return merged
            except Exception as exc:
                last_error = _sanitize_error_detail(str(exc))
                continue

        if mode == "external" and self.runtime_config.strict_external:
            raise RuntimeError(f"external reasoner failed after retries: {_sanitize_error_detail(last_error)}")
        return self._fallback(
            deterministic,
            note=f"External reasoner failed after retries; fallback deterministic. detail={_sanitize_error_detail(last_error)}",
            backend="deterministic_fallback",
        )

    def _resolve_client(self) -> tuple[ExternalAIClient | None, str]:
        if self._ai_client is not None:
            return self._ai_client, ""
        try:
            cfg = ExternalAIConfig.from_env()
            return ExternalAIClient(cfg), ""
        except Exception as exc:
            return None, str(exc)

    def _build_external_prompts(
        self,
        *,
        input_data: ReasoningInput,
        rule_package: dict[str, Any],
        deterministic: dict[str, Any],
        reasoner_template: dict[str, Any],
    ) -> tuple[str, str]:
        system_prompt = str(reasoner_template.get("system_prompt", "")).strip()
        user_instruction = str(reasoner_template.get("user_instruction", "")).strip()
        schema_hint = reasoner_template.get("output_schema", {})
        user_prompt = json.dumps(
            {
                "instruction": user_instruction,
                "query": input_data.query,
                "task_candidates": rule_package.get("task_candidates") or [],
                "method_candidates": rule_package.get("method_candidates") or [],
                "hard_constraints": rule_package.get("hard_constraints") or [],
                "warnings": rule_package.get("warnings") or [],
                "analysis_mode": rule_package.get("analysis_mode", "exploratory"),
                "sensitivity_hints": rule_package.get("sensitivity_hints") or [],
                "uncertainty_factors": rule_package.get("uncertainty_factors") or [],
                "deterministic_baseline": deterministic,
                "output_schema": schema_hint,
            },
            ensure_ascii=False,
        )
        return system_prompt, user_prompt

    def _fallback(self, baseline: dict[str, Any], *, note: str, backend: str) -> dict[str, Any]:
        out = dict(baseline)
        limitations = _to_str_list(out.get("limitations"))
        limitations.append(note)
        out["limitations"] = _dedupe(limitations)
        out["reasoner_backend"] = backend
        return out

    def _merge_external_payload(
        self,
        *,
        deterministic: dict[str, Any],
        payload: dict[str, Any],
        input_data: ReasoningInput,
        rule_package: dict[str, Any],
        client: ExternalAIClient,
        reasoner_template: dict[str, Any],
    ) -> dict[str, Any]:
        out = dict(deterministic)
        method_candidates = _to_str_list(rule_package.get("method_candidates"))
        analysis_mode = str(rule_package.get("analysis_mode", "exploratory")).strip() or "exploratory"

        strategy = payload.get("recommended_analysis_strategy")
        strategy = strategy if isinstance(strategy, dict) else {}
        primary = str(strategy.get("primary_method", "")).strip() or str(
            (deterministic.get("recommended_analysis_strategy") or {}).get("primary_method", "")
        ).strip()
        if method_candidates and primary and primary not in method_candidates:
            primary = method_candidates[0]

        secondary = _to_str_list(strategy.get("secondary_methods"))
        if method_candidates:
            filtered: list[str] = []
            for item in secondary:
                if item in method_candidates and item not in filtered:
                    filtered.append(item)
            secondary = filtered
        schema = reasoner_template.get("output_schema", {})
        max_secondary = int((schema.get("max_secondary_methods", 3) if isinstance(schema, dict) else 3) or 3)
        secondary = secondary[: max(1, max_secondary)]

        reasoning_mode = str(payload.get("reasoning_mode", "")).strip() or analysis_mode
        if reasoning_mode not in {"exploratory", "causal_inference"}:
            reasoning_mode = analysis_mode

        reasoning = _to_str_list(payload.get("reasoning")) or _to_str_list(out.get("reasoning"))
        assumptions = _to_str_list(payload.get("assumptions")) or _to_str_list(out.get("assumptions"))
        limitations = _dedupe(_to_str_list(out.get("limitations")) + _to_str_list(payload.get("limitations")))

        sensitivity_hints = _dedupe(
            _to_str_list(payload.get("sensitivity_hints")) + _to_str_list(rule_package.get("sensitivity_hints"))
        )
        uncertainty_factors = _dedupe(
            _to_str_list(payload.get("uncertainty_factors")) + _to_str_list(rule_package.get("uncertainty_factors"))
        )

        try:
            uncertainty_score = _clamp01(float(payload.get("uncertainty_score", 0.0) or 0.0))
        except Exception:
            uncertainty_score = 0.0
        if uncertainty_score <= 0.0:
            uncertainty_score = _score_uncertainty(
                factors=uncertainty_factors,
                mode=reasoning_mode,
                dataset_count=len(input_data.datasets),
            )

        uncertainty_level = str(payload.get("uncertainty_level", "")).strip().lower()
        if uncertainty_level not in {"low", "medium", "high"}:
            uncertainty_level = _to_uncertainty_level(uncertainty_score)

        inferred_goal = str(payload.get("inferred_goal", "")).strip() or str(out.get("inferred_goal", "")).strip()

        out.update(
            {
                "inferred_goal": inferred_goal,
                "reasoning_mode": reasoning_mode,
                "recommended_analysis_strategy": {
                    "primary_method": primary,
                    "secondary_methods": secondary,
                },
                "reasoning": reasoning,
                "assumptions": assumptions,
                "limitations": limitations,
                "sensitivity_hints": sensitivity_hints,
                "uncertainty_factors": uncertainty_factors,
                "uncertainty_level": uncertainty_level,
                "uncertainty_score": round(uncertainty_score, 3),
                "provider_model": f"{client.config.provider}:{client.config.model}",
            }
        )
        return out

    def _infer_deterministic(self, *, input_data: ReasoningInput, rule_package: dict[str, Any]) -> dict[str, Any]:
        task_candidates = rule_package.get("task_candidates") or ["spatial_comparison"]
        method_candidates = list(rule_package.get("method_candidates") or [])
        analysis_mode = str(rule_package.get("analysis_mode", "exploratory")).strip() or "exploratory"
        sensitivity_hints = [str(x).strip() for x in (rule_package.get("sensitivity_hints") or []) if str(x).strip()]
        uncertainty_factors = [str(x).strip() for x in (rule_package.get("uncertainty_factors") or []) if str(x).strip()]

        primary = method_candidates[0] if method_candidates else "zonal_summary"
        secondary = method_candidates[1:3] if len(method_candidates) > 1 else []

        rationale = [
            "Method chain selected from rule-layer candidates.",
            "Priority given to reproducible and interpretable geospatial workflow.",
        ]
        if analysis_mode == "causal_inference":
            rationale.append("Query indicates causal intent; treat outputs as quasi-causal hypotheses unless design is provided.")

        assumptions = [
            "Input metadata is sufficiently accurate for method selection.",
        ]
        limitations = [
            "This phase uses deterministic reasoner; advanced tradeoff is not yet enabled.",
        ]
        if "reproject_to_projected_crs_before_distance_ops" in (rule_package.get("hard_constraints") or []):
            limitations.append("Distance-related tasks require CRS preprocessing.")
        if analysis_mode == "causal_inference":
            limitations.append("Current workflow is exploratory unless identification strategy and controls are explicitly provided.")
        if "maup_or_scale_effects_should_be_reported" in (rule_package.get("warnings") or []):
            limitations.append("Results may vary with spatial aggregation units (MAUP/scale effects).")

        uncertainty_score = _score_uncertainty(
            factors=uncertainty_factors,
            mode=analysis_mode,
            dataset_count=len(input_data.datasets),
        )
        uncertainty_level = _to_uncertainty_level(uncertainty_score)

        return {
            "inferred_goal": input_data.project_context.analysis_goal or input_data.query,
            "task_candidates": task_candidates,
            "reasoning_mode": analysis_mode,
            "recommended_analysis_strategy": {
                "primary_method": primary,
                "secondary_methods": secondary,
            },
            "reasoning": rationale,
            "assumptions": assumptions,
            "limitations": limitations,
            "uncertainty_level": uncertainty_level,
            "uncertainty_score": round(uncertainty_score, 3),
            "sensitivity_hints": sensitivity_hints,
            "uncertainty_factors": uncertainty_factors,
            "provider_model": "deterministic-reasoner-v0",
        }


__all__ = ["GeoMethodReasoner", "ReasonerRuntimeConfig"]
