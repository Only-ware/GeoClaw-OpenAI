from __future__ import annotations

import re
from typing import Any

from .schemas import (
    ArtifactSpec,
    Artifacts,
    ExecutionPlan,
    InputAssessment,
    Provenance,
    ReasoningInput,
    ReasoningSummary,
    SpatialReasoningResult,
    TaskProfile,
    WorkflowOperation,
    WorkflowPlan,
)

_DISTANCE_HINT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(km|公里|m|米)?", re.IGNORECASE)


def _extract_distance_radii(query: str) -> list[int]:
    if not query.strip():
        return [300, 500, 800]
    found: list[int] = []
    for raw_num, raw_unit in _DISTANCE_HINT_RE.findall(query):
        try:
            value = float(raw_num)
        except ValueError:
            continue
        unit = str(raw_unit or "").lower()
        if unit in {"km", "公里"}:
            value *= 1000.0
        meters = int(round(value))
        if 50 <= meters <= 50000 and meters not in found:
            found.append(meters)
    if not found:
        return [300, 500, 800]
    return found[:5]


def _build_primary_parameters(*, primary_task: str, primary_method: str, input_data: ReasoningInput) -> dict[str, Any]:
    query_l = input_data.query.lower()
    if primary_task in {"proximity_analysis", "accessibility_analysis"}:
        if "buffer" in primary_method or "distance" in primary_method or "距离" in query_l:
            return {"radii_m": _extract_distance_radii(input_data.query)}
        return {"aggregation": "count"}

    if primary_task == "site_selection":
        return {
            "criteria": ["demand", "accessibility", "competition"],
            "weights": [0.45, 0.35, 0.2],
            "normalization": "minmax",
        }

    if primary_task == "change_detection":
        time_slices = sorted({x.time_range for x in input_data.datasets if x.time_range})
        return {
            "time_slices": time_slices,
            "comparison_mode": "pairwise_change",
        }

    if primary_task == "trajectory_analysis":
        return {
            "time_bin": "1H",
            "min_trip_points": 2,
        }

    return {}


def _build_optional_parameters(*, method: str, input_data: ReasoningInput) -> dict[str, Any]:
    method_l = method.lower()
    if "kernel_density" in method_l:
        return {"bandwidth_m": 500}
    if "location_allocation" in method_l:
        return {"objective": "maximize_coverage"}
    if "trend" in method_l:
        return {"trend_metric": "slope"}
    if "flow_aggregation" in method_l:
        return {"spatial_unit": "grid_1km"}
    if "buffer" in method_l or "distance" in method_l:
        return {"radii_m": _extract_distance_radii(input_data.query)}
    return {}


def synthesize_workflow(
    *,
    input_data: ReasoningInput,
    context: dict[str, Any],
    rule_package: dict[str, Any],
    llm_package: dict[str, Any],
    validation: Any,
    execution_plan: ExecutionPlan,
) -> SpatialReasoningResult:
    task_candidates = list(rule_package.get("task_candidates") or ["spatial_comparison"])
    hard_constraints = list(rule_package.get("hard_constraints") or [])
    primary_task = task_candidates[0]

    task_profile = TaskProfile(
        task_type=primary_task,
        subtask_types=["comparative_analysis"] if primary_task == "proximity_analysis" else [],
        domain="urban_computing",
        analysis_goal=llm_package.get("inferred_goal", "") or input_data.query,
        output_intent=input_data.user_context.output_preference or ["map", "summary", "workflow_trace"],
    )

    crs_values = [x.crs for x in input_data.datasets if x.crs]
    crs_status = "consistent"
    if len(set(crs_values)) > 1:
        crs_status = "inconsistent"
    if "reproject_to_projected_crs_before_distance_ops" in hard_constraints:
        crs_status = "needs_reprojection"

    assessment = InputAssessment(
        datasets_used=[x.dataset_id for x in input_data.datasets],
        crs_status=crs_status,
        extent_status="overlap_confirmed" if input_data.datasets else "unknown",
        temporal_status="single_period_analysis",
        data_quality_notes=[str(x) for x in (rule_package.get("warnings") or [])],
    )

    strategy = llm_package.get("recommended_analysis_strategy") or {}
    summary = ReasoningSummary(
        primary_method=str(strategy.get("primary_method", "")).strip(),
        secondary_methods=[str(x).strip() for x in (strategy.get("secondary_methods") or []) if str(x).strip()],
        reasoning_mode=str(llm_package.get("reasoning_mode", "exploratory")).strip() or "exploratory",
        method_selection_rationale=[str(x) for x in (llm_package.get("reasoning") or [])],
        assumptions=[str(x) for x in (llm_package.get("assumptions") or [])],
        limitations=[str(x) for x in (llm_package.get("limitations") or [])],
        uncertainty_level=str(llm_package.get("uncertainty_level", "medium")),
        uncertainty_score=float(llm_package.get("uncertainty_score", 0.0) or 0.0),
        sensitivity_hints=[str(x).strip() for x in (llm_package.get("sensitivity_hints") or []) if str(x).strip()],
        uncertainty_factors=[str(x).strip() for x in (llm_package.get("uncertainty_factors") or []) if str(x).strip()],
    )

    preconditions: list[dict[str, Any]] = []
    if "reproject_to_projected_crs_before_distance_ops" in hard_constraints:
        target_crs = input_data.project_context.default_crs or "EPSG:3857"
        for ds in input_data.datasets:
            if ds.crs.upper() in {"EPSG:4326", "EPSG:4490"}:
                preconditions.append(
                    {
                        "action": "reproject_layer",
                        "target": ds.dataset_id,
                        "to_crs": target_crs,
                    }
                )
    if "unify_crs_before_overlay" in hard_constraints and input_data.datasets:
        unify_target = input_data.project_context.default_crs or "EPSG:3857"
        preconditions.append(
            {
                "action": "unify_crs",
                "targets": [x.dataset_id for x in input_data.datasets],
                "to_crs": unify_target,
            }
        )
    if "ensure_extent_overlap" in hard_constraints and input_data.datasets:
        preconditions.append(
            {
                "action": "validate_extent_overlap",
                "targets": [x.dataset_id for x in input_data.datasets],
            }
        )

    steps: list[WorkflowOperation] = []
    primary_method = summary.primary_method or "zonal_summary"
    if primary_method:
        steps.append(
            WorkflowOperation(
                step_id="s1",
                operation_type="analysis",
                method=primary_method,
                inputs=[x.dataset_id for x in input_data.datasets[:2]],
                parameters=_build_primary_parameters(
                    primary_task=primary_task,
                    primary_method=primary_method,
                    input_data=input_data,
                ),
                expected_output="analysis_result",
            )
        )

    optional_steps: list[WorkflowOperation] = []
    for idx, method in enumerate(summary.secondary_methods, start=1):
        optional_steps.append(
            WorkflowOperation(
                step_id=f"o{idx}",
                operation_type="optional_analysis",
                method=method,
                inputs=[x.dataset_id for x in input_data.datasets[:2]],
                parameters=_build_optional_parameters(method=method, input_data=input_data),
                expected_output=f"optional_result_{idx}",
            )
        )

    workflow = WorkflowPlan(preconditions=preconditions, steps=steps, optional_steps=optional_steps)

    artifacts = Artifacts(
        expected_outputs=[
            ArtifactSpec(artifact_type="geofile", name="analysis_result.gpkg"),
            ArtifactSpec(artifact_type="report", name="analysis_summary.md"),
        ]
    )

    provenance = Provenance.create(
        source_query=input_data.query,
        llm_model=str(llm_package.get("provider_model", "deterministic-reasoner-v0")),
    )

    return SpatialReasoningResult(
        task_profile=task_profile,
        input_assessment=assessment,
        reasoning_summary=summary,
        workflow_plan=workflow,
        validation=validation,
        artifacts=artifacts,
        provenance=provenance,
        execution_plan=execution_plan,
    )
