from __future__ import annotations

from typing import Any

from .schemas import ExecutionPlan, ReasoningInput, ValidationResult


def _first_dataset_path(input_data: ReasoningInput, *, dataset_type: str = "") -> str:
    for ds in input_data.datasets:
        if dataset_type and ds.dataset_type.lower() != dataset_type.lower():
            continue
        if ds.path:
            return ds.path
    return ""


def map_execution_plan(
    *,
    input_data: ReasoningInput,
    task_type: str,
    validation: ValidationResult,
    reasoning_summary: dict[str, Any],
) -> ExecutionPlan:
    safe = validation.status != "fail"
    blocking: list[str] = []
    if not safe:
        blocking = [f"{x.code}: {x.message}" for x in validation.blocking_errors]

    if not safe:
        return ExecutionPlan(
            route_target="blocked",
            command=[],
            alternatives=[],
            safe_to_execute=False,
            blocking_reasons=blocking,
            rationale=["Validation failed; execution must be blocked."],
        )

    query_l = input_data.query.lower()
    rationale: list[str] = ["Generated from SRE task profile and policy-safe validation result."]

    if task_type == "site_selection":
        if any(x in query_l for x in ("mall", "shopping", "商场", "商业")):
            return ExecutionPlan(
                route_target="skill",
                command=["skill", "--", "--skill", "mall_site_selection_qgis", "--skip-download"],
                alternatives=[
                    ["skill", "--", "--skill", "mall_site_selection_llm"],
                    ["run", "--case", "site_selection"],
                ],
                safe_to_execute=True,
                blocking_reasons=[],
                rationale=rationale + ["Mall-like site selection favors registered QGIS skill for reproducibility."],
            )
        return ExecutionPlan(
            route_target="run",
            command=["run", "--case", "site_selection"],
            alternatives=[["skill", "--", "--skill", "site_selection"]],
            safe_to_execute=True,
            blocking_reasons=[],
            rationale=rationale + ["Site selection mapped to native run case."],
        )

    if task_type == "trajectory_analysis":
        pfs_csv = _first_dataset_path(input_data, dataset_type="trajectory") or _first_dataset_path(input_data)
        if not pfs_csv:
            pfs_csv = "data/examples/trajectory/trackintel_demo_pfs.csv"
        out_dir = "data/outputs/network_trackintel_sre"
        return ExecutionPlan(
            route_target="network",
            command=["network", "--pfs-csv", pfs_csv, "--out-dir", out_dir],
            alternatives=[["run", "--case", "wuhan_advanced"]],
            safe_to_execute=True,
            blocking_reasons=[],
            rationale=rationale + ["Trajectory analysis mapped to network command path."],
        )

    if task_type in {"accessibility_analysis", "proximity_analysis"}:
        return ExecutionPlan(
            route_target="run",
            command=["run", "--case", "location_analysis"],
            alternatives=[["operator", "--algorithm", "native:buffer"]],
            safe_to_execute=True,
            blocking_reasons=[],
            rationale=rationale + ["Accessibility/proximity tasks map to location analysis baseline."],
        )

    if task_type == "change_detection":
        return ExecutionPlan(
            route_target="run",
            command=["run", "--case", "wuhan_advanced"],
            alternatives=[["run", "--case", "location_analysis"]],
            safe_to_execute=True,
            blocking_reasons=[],
            rationale=rationale + ["Change-like workflows prefer advanced multi-step case path."],
        )

    primary = str(reasoning_summary.get("primary_method", "")).strip()
    if primary:
        return ExecutionPlan(
            route_target="operator",
            command=["operator", "--algorithm", "native:buffer"],
            alternatives=[["run", "--case", "native_cases"]],
            safe_to_execute=True,
            blocking_reasons=[],
            rationale=rationale + [f"Fallback operator route selected from primary method={primary}."],
        )

    return ExecutionPlan(
        route_target="run",
        command=["run", "--case", "native_cases"],
        alternatives=[],
        safe_to_execute=True,
        blocking_reasons=[],
        rationale=rationale + ["Default fallback route."],
    )
