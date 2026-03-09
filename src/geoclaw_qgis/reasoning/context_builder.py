from __future__ import annotations

import re
from typing import Any

from .schemas import ReasoningInput


KEYWORD_TASK_MAP: list[tuple[tuple[str, ...], str]] = [
    (("选址", "site", "location-allocation"), "site_selection"),
    (("可达", "accessibility", "catchment", "服务区"), "accessibility_analysis"),
    (("变化", "change", "扩张", "趋势"), "change_detection"),
    (("轨迹", "od", "flow", "trip", "network"), "trajectory_analysis"),
    (("buffer", "缓冲", "周边", "距离", "邻近"), "proximity_analysis"),
]


def _detect_task_hints(query: str) -> list[str]:
    text = query.lower()
    out: list[str] = []
    for terms, task in KEYWORD_TASK_MAP:
        if any(term.lower() in text for term in terms):
            out.append(task)
    return out


def _extract_geo_terms(query: str) -> list[str]:
    items = re.findall(r"[A-Za-z_]{3,}|[\u4e00-\u9fff]{2,}", query)
    out: list[str] = []
    for item in items:
        text = item.strip().lower()
        if text and text not in out:
            out.append(text)
    return out


def build_reasoning_context(input_data: ReasoningInput) -> dict[str, Any]:
    query = input_data.query.strip()
    task_hints = _detect_task_hints(query)
    if input_data.planner_hints.candidate_task_type and input_data.planner_hints.candidate_task_type not in task_hints:
        task_hints.insert(0, input_data.planner_hints.candidate_task_type)

    return {
        "query": query,
        "query_terms": _extract_geo_terms(query),
        "task_hints": task_hints,
        "dataset_ids": [x.dataset_id for x in input_data.datasets],
        "dataset_types": [x.dataset_type for x in input_data.datasets if x.dataset_type],
        "crs_values": [x.crs for x in input_data.datasets if x.crs],
        "project_context": input_data.project_context.to_dict(),
        "user_context": input_data.user_context.to_dict(),
        "planner_hints": input_data.planner_hints.to_dict(),
        "system_policy": input_data.system_policy.to_dict(),
    }
