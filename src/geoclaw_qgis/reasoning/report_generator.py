from __future__ import annotations

import json
from typing import Any

from .schemas import ReasoningInput, SpatialReasoningResult


def _fmt_list(items: list[str]) -> str:
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    if not cleaned:
        return "- (none)"
    return "\n".join(f"- {x}" for x in cleaned)


def _fmt_validation_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "- (none)"
    out: list[str] = []
    for row in rows:
        code = str(row.get("code", "")).strip() or "N/A"
        message = str(row.get("message", "")).strip() or ""
        out.append(f"- `{code}`: {message}".rstrip(": "))
    return "\n".join(out)


def render_reasoning_report(*, input_data: ReasoningInput, result: SpatialReasoningResult) -> str:
    data = result.to_dict()
    task = data.get("task_profile", {})
    summary = data.get("reasoning_summary", {})
    workflow = data.get("workflow_plan", {})
    validation = data.get("validation", {})
    assessment = data.get("input_assessment", {})
    provenance = data.get("provenance", {})

    primary = str(summary.get("primary_method", "")).strip() or "N/A"
    secondary = [str(x).strip() for x in (summary.get("secondary_methods") or []) if str(x).strip()]
    mode = str(summary.get("reasoning_mode", "exploratory")).strip() or "exploratory"
    uncertainty_level = str(summary.get("uncertainty_level", "unknown")).strip()
    uncertainty_score = float(summary.get("uncertainty_score", 0.0) or 0.0)

    lines: list[str] = []
    lines.append("# GeoClaw Spatial Reasoning Report")
    lines.append("")
    lines.append("## Overview")
    lines.append(f"- Query: {input_data.query}")
    lines.append(f"- Task Type: {task.get('task_type', '')}")
    lines.append(f"- Reasoning Mode: {mode}")
    lines.append(f"- Primary Method: {primary}")
    lines.append(f"- Secondary Methods: {', '.join(secondary) if secondary else '(none)'}")
    lines.append(f"- Uncertainty: {uncertainty_level} (score={uncertainty_score:.3f})")
    lines.append("")

    lines.append("## Data Assessment")
    lines.append(f"- Datasets Used: {', '.join(assessment.get('datasets_used', [])) or '(none)'}")
    lines.append(f"- CRS Status: {assessment.get('crs_status', 'unknown')}")
    lines.append(f"- Extent Status: {assessment.get('extent_status', 'unknown')}")
    lines.append(f"- Temporal Status: {assessment.get('temporal_status', 'unknown')}")
    lines.append("- Data Quality Notes:")
    lines.append(_fmt_list([str(x) for x in (assessment.get("data_quality_notes") or [])]))
    lines.append("")

    lines.append("## Sensitivity & Uncertainty")
    lines.append("- Sensitivity Hints:")
    lines.append(_fmt_list([str(x) for x in (summary.get("sensitivity_hints") or [])]))
    lines.append("- Uncertainty Factors:")
    lines.append(_fmt_list([str(x) for x in (summary.get("uncertainty_factors") or [])]))
    lines.append("")

    lines.append("## Method Rationale")
    lines.append(_fmt_list([str(x) for x in (summary.get("method_selection_rationale") or [])]))
    lines.append("")
    lines.append("## Assumptions")
    lines.append(_fmt_list([str(x) for x in (summary.get("assumptions") or [])]))
    lines.append("")
    lines.append("## Limitations")
    lines.append(_fmt_list([str(x) for x in (summary.get("limitations") or [])]))
    lines.append("")

    lines.append("## Workflow")
    preconditions = workflow.get("preconditions") or []
    steps = workflow.get("steps") or []
    optional_steps = workflow.get("optional_steps") or []

    lines.append("### Preconditions")
    if preconditions:
        for item in preconditions:
            lines.append(f"- `{item.get('action', 'unknown')}`: `{json.dumps(item, ensure_ascii=False)}`")
    else:
        lines.append("- (none)")

    lines.append("### Steps")
    if steps:
        for item in steps:
            sid = item.get("step_id", "")
            method = item.get("method", "")
            params = item.get("parameters", {}) or {}
            lines.append(f"- `{sid}` `{method}` params=`{json.dumps(params, ensure_ascii=False)}`")
    else:
        lines.append("- (none)")

    lines.append("### Optional Steps")
    if optional_steps:
        for item in optional_steps:
            sid = item.get("step_id", "")
            method = item.get("method", "")
            params = item.get("parameters", {}) or {}
            lines.append(f"- `{sid}` `{method}` params=`{json.dumps(params, ensure_ascii=False)}`")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Validation")
    lines.append(f"- Status: {validation.get('status', 'unknown')}")
    lines.append("- Blocking Errors:")
    lines.append(_fmt_validation_rows(validation.get("blocking_errors") or []))
    lines.append("- Warnings:")
    lines.append(_fmt_validation_rows(validation.get("warnings") or []))
    lines.append("- Required Preconditions:")
    lines.append(_fmt_list([str(x) for x in (validation.get("required_preconditions") or [])]))
    lines.append("- Revisions Applied:")
    lines.append(_fmt_list([str(x) for x in (validation.get("revisions_applied") or [])]))
    lines.append("")

    lines.append("## Provenance")
    lines.append(f"- Engine Version: {provenance.get('engine_version', '')}")
    lines.append(f"- Timestamp: {provenance.get('reasoning_timestamp', '')}")
    lines.append(f"- LLM Model: {provenance.get('llm_model', '')}")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["render_reasoning_report"]
