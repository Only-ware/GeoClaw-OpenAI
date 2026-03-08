from __future__ import annotations

from typing import Any

from geoclaw_qgis.profile import SessionProfile

from .schemas import ReasoningInput


def build_reasoning_input(
    *,
    query: str,
    user_context: dict[str, Any] | None = None,
    project_context: dict[str, Any] | None = None,
    datasets: list[dict[str, Any]] | None = None,
    planner_hints: dict[str, Any] | None = None,
    system_policy: dict[str, Any] | None = None,
) -> ReasoningInput:
    payload = {
        "query": query,
        "user_context": user_context or {},
        "project_context": project_context or {},
        "datasets": datasets or [],
        "planner_hints": planner_hints or {},
        "system_policy": system_policy or {},
    }
    return ReasoningInput.from_dict(payload)


def build_reasoning_input_from_profile(
    *,
    query: str,
    session: SessionProfile,
    datasets: list[dict[str, Any]] | None = None,
    planner_hints: dict[str, Any] | None = None,
    project_context: dict[str, Any] | None = None,
    system_policy: dict[str, Any] | None = None,
) -> ReasoningInput:
    user_context = {
        "language": session.user.preferred_language,
        "expertise": session.user.role,
        "tool_preference": session.user.preferred_tools,
        "output_preference": session.user.output_preferences,
    }
    project = dict(project_context or {})
    if not project.get("study_area") and session.user.common_project_contexts:
        project["study_area"] = session.user.common_project_contexts[0]
    if not project.get("analysis_goal"):
        project["analysis_goal"] = "spatial_reasoning"

    policy = {
        "readonly_inputs": True,
        "require_output_workspace": True,
        "allow_unregistered_tools": False,
    }
    policy.update(system_policy or {})

    return build_reasoning_input(
        query=query,
        user_context=user_context,
        project_context=project,
        datasets=datasets or [],
        planner_hints=planner_hints or {},
        system_policy=policy,
    )
