from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

import yaml

_TYPE_MAP = {
    "pipeline": "pipeline",
    "workflow": "pipeline",
    "qgis": "pipeline",
    "ai": "ai",
    "llm": "ai",
    "prompt": "ai",
    "builtin": "builtin",
    "command": "builtin",
    "cli": "builtin",
}

_ALLOWED_BUILTIN_ROOTS = {"run", "operator", "network", "reasoning"}


def _read_openclaw_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data: Any
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"OpenClaw spec must be a JSON/YAML object: {path}")
    if isinstance(data.get("skill"), dict):
        return dict(data["skill"])
    return data


def _first_text(payload: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _first_list(payload: dict[str, Any], keys: list[str]) -> list[str]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            out = [str(x).strip() for x in value if str(x).strip()]
            if out:
                return out
    return []


def _sanitize_skill_id(raw: str) -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", raw.lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "skill"


def _normalize_builtin_tokens(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [str(x).strip() for x in shlex.split(raw) if str(x).strip()]
    return []


def _split_builtin(tokens: list[str]) -> tuple[list[str], list[str]]:
    if not tokens:
        raise ValueError("OpenClaw builtin/command is empty")

    # Allow command forms:
    # - geoclaw-openai <root> ...
    # - python -m geoclaw_qgis.cli.main <root> ...
    if tokens[0] == "geoclaw-openai":
        tokens = tokens[1:]
    elif len(tokens) >= 4 and tokens[0].startswith("python") and tokens[1] == "-m" and tokens[2] == "geoclaw_qgis.cli.main":
        tokens = tokens[3:]

    if not tokens:
        raise ValueError("OpenClaw command missing root subcommand")
    root = tokens[0]
    if root not in _ALLOWED_BUILTIN_ROOTS:
        raise ValueError(
            f"OpenClaw command root '{root}' is not supported. Allowed: {sorted(_ALLOWED_BUILTIN_ROOTS)}"
        )
    return [root], tokens[1:]


def load_openclaw_skill_spec(path: str | Path, *, id_prefix: str = "openclaw_") -> dict[str, Any]:
    spec_path = Path(path).expanduser().resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"OpenClaw spec file not found: {spec_path}")

    payload = _read_openclaw_payload(spec_path)
    raw_id = _first_text(payload, ["id", "skill_id", "name", "title"]) or spec_path.stem
    sid = _sanitize_skill_id(raw_id)
    prefix = str(id_prefix or "").strip()
    if prefix and not sid.startswith(prefix):
        sid = f"{prefix}{sid}"

    description = _first_text(payload, ["description", "summary", "purpose"])
    if description:
        description = f"{description} (imported from OpenClaw)"
    else:
        description = "Imported OpenClaw skill"

    raw_type = _first_text(payload, ["type", "skill_type", "kind", "mode"]).lower()
    skill_type = _TYPE_MAP.get(raw_type, "")
    if not skill_type:
        if _first_text(payload, ["pipeline", "workflow", "path"]):
            skill_type = "pipeline"
        elif _first_text(payload, ["system_prompt", "prompt", "instruction"]):
            skill_type = "ai"
        elif _first_text(payload, ["command", "cli"]) or _first_list(payload, ["builtin"]):
            skill_type = "builtin"
        else:
            raise ValueError("Cannot infer OpenClaw skill type. Please set type/kind/skill_type.")

    out: dict[str, Any] = {
        "id": sid,
        "type": skill_type,
        "description": description,
        "openclaw_source": str(spec_path),
    }

    if skill_type == "pipeline":
        pipeline = _first_text(payload, ["pipeline", "workflow", "path"])
        if not pipeline:
            raise ValueError("OpenClaw pipeline skill missing pipeline/workflow/path")
        report_path = _first_text(payload, ["report_path", "report", "output_report"])
        if not report_path:
            report_path = f"data/outputs/{sid}/pipeline_report.json"
        out["pipeline"] = pipeline
        out["report_path"] = report_path
        pre_steps = _first_list(payload, ["pre_steps", "deps", "dependencies"])
        if pre_steps:
            out["pre_steps"] = pre_steps
        requires_osm = payload.get("requires_osm")
        if isinstance(requires_osm, bool):
            out["requires_osm"] = requires_osm
        default_bbox = _first_text(payload, ["default_bbox", "bbox"])
        if default_bbox:
            out["default_bbox"] = default_bbox
        return out

    if skill_type == "ai":
        system_prompt = _first_text(payload, ["system_prompt", "prompt", "instruction"])
        if not system_prompt:
            raise ValueError("OpenClaw ai skill missing system_prompt/prompt/instruction")
        out["system_prompt"] = system_prompt
        return out

    builtin = _first_list(payload, ["builtin"])
    if not builtin:
        tokens = _normalize_builtin_tokens(payload.get("command") or payload.get("cli"))
        if not tokens:
            raise ValueError("OpenClaw builtin skill missing builtin/command/cli")
        root, default_args = _split_builtin(tokens)
        out["builtin"] = root
        if default_args:
            out["default_args"] = default_args
    else:
        root, _ = _split_builtin(builtin)
        out["builtin"] = root
        default_args = _first_list(payload, ["default_args", "args"])
        if default_args:
            out["default_args"] = default_args
    report_path = _first_text(payload, ["report_path", "report", "output_report"])
    if report_path:
        out["report_path"] = report_path
    return out

