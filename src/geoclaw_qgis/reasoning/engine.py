from __future__ import annotations

from .context_builder import build_reasoning_context
from .execution_mapper import map_execution_plan
from .input_adapter import build_reasoning_input
from .llm_reasoner import GeoMethodReasoner
from .primitive_resolver import resolve_geo_primitives
from .rule_engine import run_rule_engine
from .schemas import ReasoningInput, SpatialReasoningResult
from .task_typer import infer_task_candidates
from .validator import validate_reasoning
from .workflow_synthesizer import synthesize_workflow


def run_spatial_reasoning(input_data: ReasoningInput) -> SpatialReasoningResult:
    context = build_reasoning_context(input_data)
    task_candidates = infer_task_candidates(input_data, context)
    primitives = resolve_geo_primitives(input_data)
    rule_package = run_rule_engine(input_data, task_candidates=task_candidates, primitives=primitives)

    reasoner = GeoMethodReasoner()
    llm_package = reasoner.infer(input_data=input_data, rule_package=rule_package)

    validation = validate_reasoning(rule_package=rule_package, llm_package=llm_package)
    execution_plan = map_execution_plan(
        input_data=input_data,
        task_type=str((rule_package.get("task_candidates") or ["spatial_comparison"])[0]),
        validation=validation,
        reasoning_summary=llm_package.get("recommended_analysis_strategy") or {},
    )
    return synthesize_workflow(
        input_data=input_data,
        context=context,
        rule_package=rule_package,
        llm_package=llm_package,
        validation=validation,
        execution_plan=execution_plan,
    )


def run_spatial_reasoning_from_payload(payload: dict[str, object]) -> SpatialReasoningResult:
    input_data = ReasoningInput.from_dict(payload)
    return run_spatial_reasoning(input_data)


__all__ = [
    "build_reasoning_input",
    "run_spatial_reasoning",
    "run_spatial_reasoning_from_payload",
]
