from __future__ import annotations

from .schemas import ReasoningInput


def infer_task_candidates(input_data: ReasoningInput, context: dict[str, object]) -> list[str]:
    candidates: list[str] = []

    hint = input_data.planner_hints.candidate_task_type.strip()
    if hint:
        candidates.append(hint)

    for item in context.get("task_hints", []):
        text = str(item).strip()
        if text and text not in candidates:
            candidates.append(text)

    if not candidates:
        candidates.append("spatial_comparison")
    return candidates
