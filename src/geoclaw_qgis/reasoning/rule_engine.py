from __future__ import annotations

import re
from typing import Any

from .config_loader import load_rule_config
from .schemas import ReasoningInput
from .template_library import methods_for


def _extent_overlap(a: list[float], b: list[float]) -> bool:
    if len(a) != 4 or len(b) != 4:
        return False
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


_DIST_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(km|公里|m|米)?", re.IGNORECASE)


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def run_rule_engine(
    input_data: ReasoningInput,
    *,
    task_candidates: list[str],
    primitives: dict[str, Any],
) -> dict[str, Any]:
    config = load_rule_config()
    keywords = config["keywords"]
    constraints = config["constraints"]
    warning_text = config["warnings"]
    geographic_crs = {str(x).upper() for x in config["crs"]["geographic"]}
    area_non_polygon = {str(x).lower() for x in config["geometry_rules"]["non_polygon_for_area_metric"]}
    trajectory_required_types = {str(x).lower() for x in config["dataset_type_rules"]["trajectory_required"]}
    accessibility_preferred_types = {str(x).lower() for x in config["dataset_type_rules"]["accessibility_preferred"]}
    change_detection_min_slices = int(config["temporal_rules"]["change_detection_min_slices"])

    hard_constraints: list[str] = []
    warnings: list[str] = []
    method_candidates: list[str] = []

    query_l = input_data.query.lower()
    crs_values = [x.crs.upper() for x in input_data.datasets if x.crs]
    dataset_types = [x.dataset_type.lower() for x in input_data.datasets if x.dataset_type]
    geometry_types = [x.geometry.lower() for x in input_data.datasets if x.geometry]
    distance_numbers = _DIST_NUM_RE.findall(query_l)

    analysis_mode = "exploratory"
    if any(x in query_l for x in keywords["causal"]):
        analysis_mode = "causal_inference"
    elif any(x in query_l for x in keywords["exploratory"]):
        analysis_mode = "exploratory"

    sensitivity_hints: list[str] = []
    uncertainty_factors: list[str] = []

    if any(k in query_l for k in keywords["distance"]):
        if any(crs in geographic_crs for crs in crs_values):
            hard_constraints.append(constraints["distance_requires_projected_crs"])

    if len(set(crs_values)) > 1:
        hard_constraints.append(constraints["unify_crs_before_overlay"])

    if input_data.system_policy.readonly_inputs:
        hard_constraints.append(constraints["readonly_inputs"])
    if input_data.system_policy.require_output_workspace:
        hard_constraints.append(constraints["workspace_output_only"])
    if not input_data.system_policy.allow_unregistered_tools:
        hard_constraints.append(constraints["registered_tools_only"])

    if input_data.datasets:
        if len(input_data.datasets) == 1:
            warnings.append(warning_text["single_dataset"])
            uncertainty_factors.append("single_dataset_context")
        has_extent = [bool(x.extent) for x in input_data.datasets]
        if not all(has_extent):
            warnings.append(warning_text["missing_extent"])
            uncertainty_factors.append("missing_extent_metadata")
        else:
            all_extents = [x.extent for x in input_data.datasets if len(x.extent) == 4]
            if len(all_extents) >= 2:
                any_overlap = False
                for i in range(len(all_extents)):
                    for j in range(i + 1, len(all_extents)):
                        if _extent_overlap(all_extents[i], all_extents[j]):
                            any_overlap = True
                            break
                    if any_overlap:
                        break
                if not any_overlap:
                    hard_constraints.append(constraints["ensure_extent_overlap"])
                    warnings.append(warning_text["extent_non_overlap"])
                    uncertainty_factors.append("extent_non_overlap")
    else:
        warnings.append(warning_text["no_datasets"])
        uncertainty_factors.append("no_dataset_attached")

    if any(task == "change_detection" for task in task_candidates):
        time_slices = sorted({x.time_range for x in input_data.datasets if x.time_range})
        if len(time_slices) < change_detection_min_slices:
            hard_constraints.append(constraints["change_detection_requires_multiple_time_slices"])
            warnings.append(warning_text["insufficient_temporal_slices"])

    if any(task == "trajectory_analysis" for task in task_candidates):
        if not any(t in trajectory_required_types for t in dataset_types):
            hard_constraints.append(constraints["trajectory_requires_data"])

    if any(task == "accessibility_analysis" for task in task_candidates):
        if not any(t in accessibility_preferred_types for t in dataset_types):
            warnings.append(warning_text["accessibility_prefers_network"])

    if any(x in query_l for x in keywords["area"]) and geometry_types:
        if all(g in area_non_polygon for g in geometry_types):
            warnings.append(warning_text["area_metric_non_polygon"])

    for task in task_candidates:
        for method in methods_for(task):
            if method not in method_candidates:
                method_candidates.append(method)

    planner_methods = input_data.planner_hints.candidate_methods
    for method in planner_methods:
        if method not in method_candidates:
            method_candidates.append(method)

    if any(x in query_l for x in keywords["scale"]):
        warnings.append(warning_text["maup_scale"])
        sensitivity_hints.append("spatial_scale_sensitivity")
        uncertainty_factors.append("maup_scale_effect")

    if any(k in query_l for k in keywords["distance"]):
        sensitivity_hints.append("buffer_radius_sensitivity")
        if len(distance_numbers) <= 1:
            uncertainty_factors.append("single_distance_parameter")

    if any(task == "site_selection" for task in task_candidates):
        sensitivity_hints.append("criteria_weight_sensitivity")

    if any(task == "change_detection" for task in task_candidates):
        sensitivity_hints.append("temporal_window_sensitivity")

    if analysis_mode == "causal_inference":
        warnings.append(warning_text.get("causal_requires_design", "causal_claim_requires_identification_strategy"))
        uncertainty_factors.append("causal_identification_missing")

    if len(set(crs_values)) > 1:
        uncertainty_factors.append("crs_mismatch")

    return {
        "task_candidates": task_candidates,
        "resolved_primitives": primitives,
        "hard_constraints": hard_constraints,
        "method_candidates": method_candidates,
        "warnings": _dedupe(warnings),
        "analysis_mode": analysis_mode,
        "sensitivity_hints": _dedupe(sensitivity_hints),
        "uncertainty_factors": _dedupe(uncertainty_factors),
    }
