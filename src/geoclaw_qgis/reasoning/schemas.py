from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_str_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


@dataclass(frozen=True)
class UserContext:
    language: str = ""
    expertise: str = ""
    tool_preference: list[str] = field(default_factory=list)
    output_preference: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> UserContext:
        p = payload or {}
        return cls(
            language=str(p.get("language", "")).strip(),
            expertise=str(p.get("expertise", "")).strip(),
            tool_preference=_to_str_list(p.get("tool_preference")),
            output_preference=_to_str_list(p.get("output_preference")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "expertise": self.expertise,
            "tool_preference": list(self.tool_preference),
            "output_preference": list(self.output_preference),
        }


@dataclass(frozen=True)
class ProjectContext:
    study_area: str = ""
    default_crs: str = ""
    analysis_goal: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> ProjectContext:
        p = payload or {}
        return cls(
            study_area=str(p.get("study_area", "")).strip(),
            default_crs=str(p.get("default_crs", "")).strip(),
            analysis_goal=str(p.get("analysis_goal", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_area": self.study_area,
            "default_crs": self.default_crs,
            "analysis_goal": self.analysis_goal,
        }


@dataclass(frozen=True)
class DatasetMeta:
    dataset_id: str
    path: str = ""
    dataset_type: str = ""
    geometry: str = ""
    crs: str = ""
    extent: list[float] = field(default_factory=list)
    time_range: str = ""
    attributes: list[str] = field(default_factory=list)
    writable: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DatasetMeta:
        did = str(payload.get("id", "")).strip()
        if not did:
            raise ValueError("dataset id is required")

        extent_raw = payload.get("extent")
        extent: list[float] = []
        if isinstance(extent_raw, list):
            for item in extent_raw:
                try:
                    extent.append(float(item))
                except Exception:
                    continue

        return cls(
            dataset_id=did,
            path=str(payload.get("path", "")).strip(),
            dataset_type=str(payload.get("type", "")).strip(),
            geometry=str(payload.get("geometry", "")).strip(),
            crs=str(payload.get("crs", "")).strip(),
            extent=extent,
            time_range=str(payload.get("time_range", "") or "").strip(),
            attributes=_to_str_list(payload.get("attributes")),
            writable=bool(payload.get("writable", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.dataset_id,
            "path": self.path,
            "type": self.dataset_type,
            "geometry": self.geometry,
            "crs": self.crs,
            "extent": list(self.extent),
            "time_range": self.time_range or None,
            "attributes": list(self.attributes),
            "writable": self.writable,
        }


@dataclass(frozen=True)
class PlannerHints:
    candidate_task_type: str = ""
    candidate_methods: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> PlannerHints:
        p = payload or {}
        return cls(
            candidate_task_type=str(p.get("candidate_task_type", "")).strip(),
            candidate_methods=_to_str_list(p.get("candidate_methods")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_task_type": self.candidate_task_type,
            "candidate_methods": list(self.candidate_methods),
        }


@dataclass(frozen=True)
class SystemPolicy:
    readonly_inputs: bool = True
    require_output_workspace: bool = True
    allow_unregistered_tools: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> SystemPolicy:
        p = payload or {}
        return cls(
            readonly_inputs=bool(p.get("readonly_inputs", True)),
            require_output_workspace=bool(p.get("require_output_workspace", True)),
            allow_unregistered_tools=bool(p.get("allow_unregistered_tools", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "readonly_inputs": self.readonly_inputs,
            "require_output_workspace": self.require_output_workspace,
            "allow_unregistered_tools": self.allow_unregistered_tools,
        }


@dataclass(frozen=True)
class ReasoningInput:
    query: str
    user_context: UserContext = field(default_factory=UserContext)
    project_context: ProjectContext = field(default_factory=ProjectContext)
    datasets: list[DatasetMeta] = field(default_factory=list)
    planner_hints: PlannerHints = field(default_factory=PlannerHints)
    system_policy: SystemPolicy = field(default_factory=SystemPolicy)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ReasoningInput:
        query = str(payload.get("query", "")).strip()
        if not query:
            raise ValueError("reasoning query is required")

        datasets_raw = payload.get("datasets")
        datasets: list[DatasetMeta] = []
        if isinstance(datasets_raw, list):
            for item in datasets_raw:
                if isinstance(item, dict):
                    datasets.append(DatasetMeta.from_dict(item))

        return cls(
            query=query,
            user_context=UserContext.from_dict(payload.get("user_context") if isinstance(payload.get("user_context"), dict) else {}),
            project_context=ProjectContext.from_dict(
                payload.get("project_context") if isinstance(payload.get("project_context"), dict) else {}
            ),
            datasets=datasets,
            planner_hints=PlannerHints.from_dict(payload.get("planner_hints") if isinstance(payload.get("planner_hints"), dict) else {}),
            system_policy=SystemPolicy.from_dict(payload.get("system_policy") if isinstance(payload.get("system_policy"), dict) else {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "user_context": self.user_context.to_dict(),
            "project_context": self.project_context.to_dict(),
            "datasets": [x.to_dict() for x in self.datasets],
            "planner_hints": self.planner_hints.to_dict(),
            "system_policy": self.system_policy.to_dict(),
        }


@dataclass(frozen=True)
class TaskProfile:
    task_type: str = "unknown"
    subtask_types: list[str] = field(default_factory=list)
    domain: str = ""
    analysis_goal: str = ""
    output_intent: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "subtask_types": list(self.subtask_types),
            "domain": self.domain,
            "analysis_goal": self.analysis_goal,
            "output_intent": list(self.output_intent),
        }


@dataclass(frozen=True)
class InputAssessment:
    datasets_used: list[str] = field(default_factory=list)
    crs_status: str = "unknown"
    extent_status: str = "unknown"
    temporal_status: str = "unknown"
    data_quality_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "datasets_used": list(self.datasets_used),
            "crs_status": self.crs_status,
            "extent_status": self.extent_status,
            "temporal_status": self.temporal_status,
            "data_quality_notes": list(self.data_quality_notes),
        }


@dataclass(frozen=True)
class ReasoningSummary:
    primary_method: str = ""
    secondary_methods: list[str] = field(default_factory=list)
    reasoning_mode: str = "exploratory"
    method_selection_rationale: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    uncertainty_level: str = "unknown"
    uncertainty_score: float = 0.0
    sensitivity_hints: list[str] = field(default_factory=list)
    uncertainty_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_method": self.primary_method,
            "secondary_methods": list(self.secondary_methods),
            "reasoning_mode": self.reasoning_mode,
            "method_selection_rationale": list(self.method_selection_rationale),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "uncertainty_level": self.uncertainty_level,
            "uncertainty_score": float(self.uncertainty_score),
            "sensitivity_hints": list(self.sensitivity_hints),
            "uncertainty_factors": list(self.uncertainty_factors),
        }


@dataclass(frozen=True)
class WorkflowOperation:
    step_id: str
    operation_type: str
    method: str
    inputs: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "operation_type": self.operation_type,
            "method": self.method,
            "inputs": list(self.inputs),
            "parameters": dict(self.parameters),
            "expected_output": self.expected_output,
        }


@dataclass(frozen=True)
class WorkflowPlan:
    preconditions: list[dict[str, Any]] = field(default_factory=list)
    steps: list[WorkflowOperation] = field(default_factory=list)
    optional_steps: list[WorkflowOperation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preconditions": [dict(x) for x in self.preconditions],
            "steps": [x.to_dict() for x in self.steps],
            "optional_steps": [x.to_dict() for x in self.optional_steps],
        }


@dataclass(frozen=True)
class ValidationMessage:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ValidationResult:
    status: str = "pass"
    blocking_errors: list[ValidationMessage] = field(default_factory=list)
    warnings: list[ValidationMessage] = field(default_factory=list)
    policy_compliance: dict[str, Any] = field(default_factory=dict)
    required_preconditions: list[str] = field(default_factory=list)
    revisions_applied: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blocking_errors": [x.to_dict() for x in self.blocking_errors],
            "warnings": [x.to_dict() for x in self.warnings],
            "policy_compliance": dict(self.policy_compliance),
            "required_preconditions": list(self.required_preconditions),
            "revisions_applied": list(self.revisions_applied),
        }


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_type: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.artifact_type, "name": self.name}


@dataclass(frozen=True)
class Artifacts:
    expected_outputs: list[ArtifactSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"expected_outputs": [x.to_dict() for x in self.expected_outputs]}


@dataclass(frozen=True)
class Provenance:
    engine_version: str
    reasoning_timestamp: str
    source_query: str
    rule_sets_used: list[str] = field(default_factory=list)
    llm_model: str = ""

    @classmethod
    def create(cls, *, source_query: str, llm_model: str = "") -> Provenance:
        return cls(
            engine_version="sre-0.1",
            reasoning_timestamp=_utc_now(),
            source_query=source_query,
            rule_sets_used=["geo_rules_v1", "method_templates_v1"],
            llm_model=llm_model,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "reasoning_timestamp": self.reasoning_timestamp,
            "source_query": self.source_query,
            "rule_sets_used": list(self.rule_sets_used),
            "llm_model": self.llm_model,
        }


@dataclass(frozen=True)
class ExecutionPlan:
    route_target: str = ""
    command: list[str] = field(default_factory=list)
    alternatives: list[list[str]] = field(default_factory=list)
    safe_to_execute: bool = False
    blocking_reasons: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_target": self.route_target,
            "command": list(self.command),
            "alternatives": [list(x) for x in self.alternatives],
            "safe_to_execute": self.safe_to_execute,
            "blocking_reasons": list(self.blocking_reasons),
            "rationale": list(self.rationale),
        }


@dataclass(frozen=True)
class SpatialReasoningResult:
    task_profile: TaskProfile
    input_assessment: InputAssessment
    reasoning_summary: ReasoningSummary
    workflow_plan: WorkflowPlan
    validation: ValidationResult
    artifacts: Artifacts
    provenance: Provenance
    execution_plan: ExecutionPlan = field(default_factory=ExecutionPlan)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_profile": self.task_profile.to_dict(),
            "input_assessment": self.input_assessment.to_dict(),
            "reasoning_summary": self.reasoning_summary.to_dict(),
            "workflow_plan": self.workflow_plan.to_dict(),
            "validation": self.validation.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "provenance": self.provenance.to_dict(),
            "execution_plan": self.execution_plan.to_dict(),
        }
