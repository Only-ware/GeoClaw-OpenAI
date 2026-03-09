from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_SKILL_TYPES = {"pipeline", "ai", "builtin"}
ALLOWED_BUILTIN_ROOTS = {"run", "operator", "network", "reasoning"}

_HIGH_RISK_PATTERNS = (
    (re.compile(r"\brm\s+-rf\b", re.IGNORECASE), "Destructive shell command pattern detected."),
    (re.compile(r"\bdel\s+/f\b", re.IGNORECASE), "Destructive Windows delete command pattern detected."),
    (re.compile(r"\bdrop\s+table\b", re.IGNORECASE), "Potential destructive SQL pattern detected."),
    (re.compile(r"\bos\.system\(", re.IGNORECASE), "Dynamic shell execution pattern detected."),
    (re.compile(r"\bsubprocess\.", re.IGNORECASE), "Subprocess execution pattern detected."),
    (re.compile(r"(\|\||&&|;|\$\()", re.IGNORECASE), "Shell chaining or command substitution pattern detected."),
    (
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        "Prompt-injection style instruction detected.",
    ),
)

_MEDIUM_RISK_PATTERNS = (
    (re.compile(r"\bcurl\b", re.IGNORECASE), "External network command keyword detected."),
    (re.compile(r"\bwget\b", re.IGNORECASE), "External network command keyword detected."),
    (re.compile(r"\bssh\b", re.IGNORECASE), "Remote shell keyword detected."),
    (re.compile(r"\bscp\b", re.IGNORECASE), "Remote copy keyword detected."),
    (re.compile(r"\b(api[_ -]?key|token|secret|password)\b", re.IGNORECASE), "Sensitive credential keyword detected."),
    (re.compile(r"\bexfiltrat(e|ion)\b", re.IGNORECASE), "Potential data-exfiltration keyword detected."),
)


@dataclass(frozen=True)
class SkillFinding:
    severity: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"severity": self.severity, "code": self.code, "message": self.message}


def _skill_text_blob(skill: dict[str, Any]) -> str:
    fields = [
        str(skill.get("id", "")),
        str(skill.get("description", "")),
        str(skill.get("pipeline", "")),
        " ".join(str(x) for x in (skill.get("builtin") or [])),
        " ".join(str(x) for x in (skill.get("default_args") or [])),
        str(skill.get("report_path", "")),
        str(skill.get("system_prompt", "")),
        " ".join(str(x) for x in (skill.get("pre_steps") or [])),
    ]
    return "\n".join(fields)


def _path_within(path_text: str, workspace_root: Path, *, must_under: str = "") -> tuple[bool, str]:
    raw = (path_text or "").strip()
    if not raw:
        return False, "empty path"
    path = Path(raw)
    if path.is_absolute():
        return False, f"absolute path not allowed: {raw}"
    if ".." in path.parts:
        return False, f"path traversal not allowed: {raw}"
    if must_under and not raw.startswith(must_under):
        return False, f"path must be under '{must_under}': {raw}"
    resolved = (workspace_root / path).resolve()
    try:
        resolved.relative_to(workspace_root.resolve())
    except ValueError:
        return False, f"path escapes workspace root: {raw}"
    return True, ""


def assess_skill_spec(
    skill: dict[str, Any],
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    findings: list[SkillFinding] = []
    skill_id = str(skill.get("id", "")).strip()
    skill_type = str(skill.get("type", "")).strip().lower()

    if not skill_id:
        findings.append(SkillFinding("high", "MISSING_ID", "Skill id is required."))
    elif not re.fullmatch(r"[a-z0-9_]+", skill_id):
        findings.append(SkillFinding("medium", "ID_FORMAT", "Skill id should match [a-z0-9_]+."))

    if skill_type not in ALLOWED_SKILL_TYPES:
        findings.append(
            SkillFinding(
                "high",
                "UNSUPPORTED_TYPE",
                f"Unsupported skill type: '{skill_type}'. Allowed: {sorted(ALLOWED_SKILL_TYPES)}.",
            )
        )

    if skill_type == "pipeline":
        pipeline = str(skill.get("pipeline", "")).strip()
        if not pipeline:
            findings.append(SkillFinding("high", "MISSING_PIPELINE", "Pipeline skill requires 'pipeline' path."))
        else:
            ok, reason = _path_within(pipeline, workspace_root, must_under="pipelines/")
            if not ok:
                findings.append(SkillFinding("high", "PIPELINE_PATH", reason))
            elif not pipeline.lower().endswith((".yaml", ".yml")):
                findings.append(SkillFinding("medium", "PIPELINE_EXT", "Pipeline file should be .yaml or .yml."))
            elif not (workspace_root / pipeline).is_file():
                findings.append(SkillFinding("medium", "PIPELINE_MISSING", f"Pipeline file not found: {pipeline}"))

        report_path = str(skill.get("report_path", "")).strip()
        if not report_path:
            findings.append(SkillFinding("medium", "MISSING_REPORT_PATH", "Pipeline skill should define report_path."))
        else:
            ok, reason = _path_within(report_path, workspace_root, must_under="data/outputs/")
            if not ok:
                findings.append(SkillFinding("high", "REPORT_PATH", reason))

    if skill_type == "ai":
        system_prompt = str(skill.get("system_prompt", "")).strip()
        if not system_prompt:
            findings.append(SkillFinding("high", "MISSING_SYSTEM_PROMPT", "AI skill requires non-empty system_prompt."))
        elif len(system_prompt) > 8000:
            findings.append(SkillFinding("medium", "PROMPT_TOO_LONG", "system_prompt is very long (>8000 chars)."))

    if skill_type == "builtin":
        builtin = [str(x).strip() for x in (skill.get("builtin") or []) if str(x).strip()]
        if not builtin:
            findings.append(SkillFinding("high", "MISSING_BUILTIN", "Builtin skill requires non-empty 'builtin' command list."))
        else:
            root = builtin[0]
            if root not in ALLOWED_BUILTIN_ROOTS:
                findings.append(
                    SkillFinding(
                        "high",
                        "BUILTIN_ROOT",
                        f"Unsupported builtin root: '{root}'. Allowed: {sorted(ALLOWED_BUILTIN_ROOTS)}.",
                    )
                )
        default_args = skill.get("default_args") or []
        if not isinstance(default_args, list):
            findings.append(SkillFinding("medium", "DEFAULT_ARGS_TYPE", "default_args should be a list of strings."))

    blob = _skill_text_blob(skill)
    for pattern, msg in _HIGH_RISK_PATTERNS:
        if pattern.search(blob):
            findings.append(SkillFinding("high", "DANGEROUS_PATTERN", msg))
    for pattern, msg in _MEDIUM_RISK_PATTERNS:
        if pattern.search(blob):
            findings.append(SkillFinding("medium", "SUSPICIOUS_PATTERN", msg))

    risk_rank = {"low": 0, "medium": 1, "high": 2}
    max_risk = "low"
    for item in findings:
        if risk_rank[item.severity] > risk_rank[max_risk]:
            max_risk = item.severity

    score = 0
    for item in findings:
        if item.severity == "medium":
            score += 3
        elif item.severity == "high":
            score += 8

    allowed = max_risk != "high"
    return {
        "skill_id": skill_id,
        "skill_type": skill_type,
        "risk_level": max_risk,
        "risk_score": score,
        "allowed_without_override": allowed,
        "findings": [x.as_dict() for x in findings],
    }


def load_skill_spec_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"skill spec must be a JSON object: {path}")
    return payload


def upsert_skill_registry(
    registry_path: Path,
    *,
    skill_spec: dict[str, Any],
    replace: bool = False,
) -> dict[str, Any]:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid registry JSON: {registry_path}")

    items = payload.get("skills")
    if not isinstance(items, list):
        raise ValueError(f"registry missing 'skills' list: {registry_path}")

    skill_id = str(skill_spec.get("id", "")).strip()
    if not skill_id:
        raise ValueError("skill id is required")

    idx = -1
    for i, it in enumerate(items):
        if isinstance(it, dict) and str(it.get("id", "")).strip() == skill_id:
            idx = i
            break

    action = "added"
    if idx >= 0:
        if not replace:
            raise ValueError(f"skill id already exists: {skill_id}. Use --replace to overwrite.")
        items[idx] = skill_spec
        action = "replaced"
    else:
        items.append(skill_spec)

    registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"skill_id": skill_id, "action": action, "registry": str(registry_path)}
