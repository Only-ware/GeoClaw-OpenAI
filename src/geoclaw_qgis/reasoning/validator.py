from __future__ import annotations

from typing import Any

from .schemas import ValidationMessage, ValidationResult


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def validate_reasoning(
    *,
    rule_package: dict[str, Any],
    llm_package: dict[str, Any],
) -> ValidationResult:
    errors: list[ValidationMessage] = []
    warnings: list[ValidationMessage] = []

    hard_constraints = list(rule_package.get("hard_constraints") or [])
    task_candidates = list(rule_package.get("task_candidates") or [])
    analysis_mode = str(rule_package.get("analysis_mode", "exploratory")).strip() or "exploratory"
    primary = str((llm_package.get("recommended_analysis_strategy") or {}).get("primary_method", "")).strip()
    reasoning_mode = str(llm_package.get("reasoning_mode", "")).strip() or analysis_mode
    sensitivity_hints = [str(x).strip() for x in (llm_package.get("sensitivity_hints") or []) if str(x).strip()]
    uncertainty_level = str(llm_package.get("uncertainty_level", "unknown")).strip().lower()
    try:
        uncertainty_score = float(llm_package.get("uncertainty_score", 0.0) or 0.0)
    except Exception:
        uncertainty_score = 0.0
    required_preconditions: list[str] = []
    revisions_applied: list[str] = []

    if not primary:
        errors.append(ValidationMessage(code="MISSING_PRIMARY_METHOD", message="No primary method selected."))

    if "trajectory_task_requires_trajectory_or_network_data" in hard_constraints:
        errors.append(
            ValidationMessage(
                code="TRAJECTORY_DATA_REQUIRED",
                message="Trajectory/network dataset is required for trajectory analysis.",
            )
        )

    if "change_detection_requires_multiple_time_slices" in hard_constraints:
        errors.append(
            ValidationMessage(
                code="TEMPORAL_SLICES_REQUIRED",
                message="At least two time slices are required for change detection.",
            )
        )

    if task_candidates and task_candidates[0] == "site_selection" and "allocation" not in primary and "overlay" not in primary:
        warnings.append(
            ValidationMessage(
                code="SITE_SELECTION_METHOD_WEAK",
                message="Site selection usually needs allocation/overlay style method.",
            )
        )

    if analysis_mode == "causal_inference":
        required_preconditions.append("provide_identification_strategy")
        warnings.append(
            ValidationMessage(
                code="CAUSAL_GUARDRAIL_REQUIRED",
                message="Causal intent detected; provide identification strategy and confounder controls.",
            )
        )
        if reasoning_mode != "causal_inference":
            warnings.append(
                ValidationMessage(
                    code="REASONING_MODE_MISMATCH",
                    message="Rule layer infers causal intent, but reasoner mode is not causal.",
                )
            )

    if "reproject_to_projected_crs_before_distance_ops" in hard_constraints:
        required_preconditions.append("reproject_to_metric_crs")
        revisions_applied.append("buffer_operation_moved_after_reprojection")
        warnings.append(
            ValidationMessage(
                code="CRS_PRECONDITION_REQUIRED",
                message="CRS reprojection precondition is required before distance operations.",
            )
        )
    if "ensure_extent_overlap" in hard_constraints:
        required_preconditions.append("ensure_dataset_extent_overlap")
        revisions_applied.append("overlay_operations_guarded_by_extent_overlap_check")
        warnings.append(
            ValidationMessage(
                code="EXTENT_OVERLAP_REQUIRED",
                message="Datasets should overlap in extent before spatial overlay analysis.",
            )
        )
    if "unify_crs_before_overlay" in hard_constraints:
        required_preconditions.append("unify_crs_before_overlay")
        revisions_applied.append("overlay_operations_guarded_by_crs_unification")
    if "change_detection_requires_multiple_time_slices" in hard_constraints:
        required_preconditions.append("attach_at_least_two_time_slices")
    if "trajectory_task_requires_trajectory_or_network_data" in hard_constraints:
        required_preconditions.append("attach_trajectory_or_network_dataset")

    for raw in rule_package.get("warnings") or []:
        text = str(raw).strip()
        if text:
            warnings.append(ValidationMessage(code="RULE_WARNING", message=text))

    if any("maup_or_scale_effects_should_be_reported" in str(x) for x in (rule_package.get("warnings") or [])):
        limitations = [str(x).lower() for x in (llm_package.get("limitations") or [])]
        if not any(("maup" in x) or ("scale" in x) or ("尺度" in x) for x in limitations):
            warnings.append(
                ValidationMessage(
                    code="SCALE_EFFECTS_NOT_EXPLAINED",
                    message="Scale/MAUP effects should be explicitly stated in limitations.",
                )
            )

    if any(
        x in task_candidates
        for x in ("proximity_analysis", "accessibility_analysis", "site_selection", "change_detection")
    ):
        if not sensitivity_hints:
            warnings.append(
                ValidationMessage(
                    code="MISSING_SENSITIVITY_HINTS",
                    message="Reasoning should include parameter sensitivity hints for this task type.",
                )
            )

    if uncertainty_level == "unknown" or uncertainty_score <= 0.0:
        warnings.append(
            ValidationMessage(
                code="MISSING_UNCERTAINTY_SCORE",
                message="Reasoning output should provide uncertainty level and score.",
            )
        )

    limitations = llm_package.get("limitations")
    if not isinstance(limitations, list) or not [x for x in limitations if str(x).strip()]:
        warnings.append(
            ValidationMessage(
                code="MISSING_LIMITATIONS",
                message="Reasoning output should include limitations/uncertainty notes.",
            )
        )

    status = "pass"
    if errors:
        status = "fail"
    elif warnings:
        status = "pass_with_warnings"

    policy = {
        "readonly_inputs": "do_not_overwrite_input" in hard_constraints,
        "workspace_output_only": "workspace_output_only" in hard_constraints,
        "registered_tools_only": "registered_tools_only" in hard_constraints,
    }

    return ValidationResult(
        status=status,
        blocking_errors=errors,
        warnings=warnings,
        policy_compliance=policy,
        required_preconditions=_dedupe(required_preconditions),
        revisions_applied=_dedupe(revisions_applied),
    )
