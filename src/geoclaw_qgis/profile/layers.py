from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoclaw_qgis.config import geoclaw_home


DEFAULT_SOUL_TEMPLATE = """# Soul.md

## Identity
GeoClaw is a geospatial reasoning and workflow agent designed to assist users in spatial analysis, geographic data processing, and GeoAI-driven research.

## Mission
Help users perform reliable, transparent, and reproducible geospatial analysis.

## Core Principles
- Prefer structured geospatial workflows over ad-hoc code execution.
- Prefer registered geospatial tools over arbitrary scripts.
- Never overwrite original user data.
- Always keep analysis reproducible when possible.
- Explicitly state uncertainty or assumptions.
- Maintain spatial reasoning consistency (CRS, scale, topology).

## Spatial Reasoning Guidelines
- Always check coordinate reference systems (CRS).
- Consider spatial scale and MAUP effects.
- Validate spatial and temporal coverage before drawing conclusions.
- Distinguish exploratory analysis from causal inference.
- Prefer interpretable geospatial methods when appropriate.

## Execution Hierarchy
1. Registered GeoClaw skills
2. QGIS / qgis_process tools
3. GDAL / OGR tools
4. Spatial SQL (PostGIS / DuckDB)
5. Controlled Python geospatial libraries

## Data Handling Rules
- Treat input datasets as read-only.
- Store outputs in the workspace output directory.
- Preserve intermediate artifacts when analysis complexity requires traceability.

## Output Standards
- method summary
- spatial assumptions
- limitations
- data source references
- reproducible workflow description

## Safety Boundaries
- do not execute high-risk unregistered tools
- do not leak credentials
- do not overwrite original data
- do not fabricate data sources

## Collaboration Philosophy
- assist reasoning rather than replace user judgement
- document analytical steps
- explain spatial logic behind results
"""


DEFAULT_USER_TEMPLATE = """# User.md

## Identity
Role: geospatial analyst or researcher
Domain: GIS / geospatial data analysis

## Language Preference
Preferred language: Chinese or English

## Communication Style
- concise explanations
- structured responses
- step-by-step workflows for complex analysis

## Tool Preferences
- QGIS
- GDAL / OGR
- Python geospatial stack (GeoPandas / Rasterio)
- PostGIS / DuckDB when needed

## Output Preferences
- maps
- geospatial datasets
- concise analysis summaries
- reproducible workflows

## Reproducibility Expectations
- keep parameterized workflows
- keep traceable intermediate outputs for complex tasks
- keep method, assumptions, and data references explicit

## Data Handling Preferences
- preserve original datasets
- store outputs in a dedicated workspace

## Common Project Contexts
- urban spatial analysis
- site selection and location intelligence
- mobility network analysis

## Long-term Constraints and Habits
- prefer incremental iteration
- prioritize verifiable results

## Privacy and Safety
- avoid exposing private paths unless necessary
- never reveal credentials
"""


_HEADER_RE = re.compile(r"^#{2,3}\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^(?:[-*]|\d+\.)\s+(.*)$")
_KV_RE = re.compile(r"^([a-zA-Z0-9_]+)\s*:\s*(.+)$")

_USER_OVERRIDE_SECTION = "Dialogue Overrides"
_SOUL_OVERRIDE_SECTION = "Dialogue Overrides (Non-Safety)"
_USER_OVERRIDE_ALIASES = ("dialogue overrides", "conversation overrides", "对话覆盖")
_SOUL_OVERRIDE_ALIASES = (
    "dialogue overrides (non-safety)",
    "conversation overrides (non-safety)",
    "对话覆盖（非安全）",
)

_USER_OVERRIDE_SCHEMA: dict[str, str] = {
    "role": "scalar",
    "domain_background": "scalar",
    "preferred_language": "scalar",
    "preferred_tone": "scalar",
    "preferred_tools": "list",
    "output_preferences": "list",
    "reproducibility_expectations": "list",
    "privacy_preferences": "list",
    "common_project_contexts": "list",
    "long_term_constraints": "list",
    "workflow_habits": "list",
}

_SOUL_OVERRIDE_SCHEMA: dict[str, str] = {
    "mission": "scalar",
    "reasoning_philosophy": "scalar",
    "spatial_reasoning_guidelines": "list",
    "output_quality_standards": "list",
    "collaboration_philosophy": "list",
}

_SOUL_LOCKED_KEYS = {
    "safety_boundaries",
    "execution_hierarchy",
    "data_handling_rules",
    "geospatial_principles",
    "truthfulness_rules",
    "reproducibility_requirements",
}


@dataclass(frozen=True)
class SoulConfig:
    identity: str
    mission: str
    reasoning_philosophy: str
    geospatial_principles: list[str]
    safety_boundaries: list[str]
    reproducibility_requirements: list[str]
    execution_hierarchy: list[str]
    truthfulness_rules: list[str]
    output_quality_standards: list[str]
    collaboration_philosophy: list[str]
    data_handling_rules: list[str]
    spatial_reasoning_guidelines: list[str]
    raw_text: str


@dataclass(frozen=True)
class UserProfile:
    role: str
    domain_background: str
    preferred_language: str
    preferred_tone: str
    preferred_tools: list[str]
    output_preferences: list[str]
    reproducibility_expectations: list[str]
    privacy_preferences: list[str]
    common_project_contexts: list[str]
    long_term_constraints: list[str]
    workflow_habits: list[str]
    raw_text: str


@dataclass(frozen=True)
class SessionProfile:
    soul: SoulConfig
    user: UserProfile
    soul_path: str
    user_path: str
    loaded_at: str

    def planner_context(self) -> dict[str, Any]:
        return {
            "preferred_language": self.user.preferred_language,
            "preferred_tone": self.user.preferred_tone,
            "preferred_tools": self.user.preferred_tools,
            "common_contexts": self.user.common_project_contexts,
            "core_principles": self.soul.geospatial_principles,
            "spatial_guidelines": self.soul.spatial_reasoning_guidelines,
            "execution_hierarchy": self.soul.execution_hierarchy,
        }

    def tool_router_context(self) -> dict[str, Any]:
        return {
            "execution_hierarchy": self.soul.execution_hierarchy,
            "safety_boundaries": self.soul.safety_boundaries,
            "preferred_tools": self.user.preferred_tools,
        }

    def report_context(self) -> dict[str, Any]:
        return {
            "mission": self.soul.mission,
            "output_quality_standards": self.soul.output_quality_standards,
            "reproducibility_requirements": self.soul.reproducibility_requirements,
            "user_output_preferences": self.user.output_preferences,
        }

    def memory_context(self) -> dict[str, Any]:
        return {
            "user_role": self.user.role,
            "preferred_tone": self.user.preferred_tone,
            "reproducibility_expectations": self.user.reproducibility_expectations,
            "long_term_constraints": self.user.long_term_constraints,
            "truthfulness_rules": self.soul.truthfulness_rules,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "loaded_at": self.loaded_at,
            "soul_path": self.soul_path,
            "user_path": self.user_path,
            "soul": {
                "mission": self.soul.mission,
                "execution_hierarchy": self.soul.execution_hierarchy,
                "geospatial_principles": self.soul.geospatial_principles,
                "safety_boundaries": self.soul.safety_boundaries,
                "output_quality_standards": self.soul.output_quality_standards,
            },
            "user": {
                "role": self.user.role,
                "domain_background": self.user.domain_background,
                "preferred_language": self.user.preferred_language,
                "preferred_tone": self.user.preferred_tone,
                "preferred_tools": self.user.preferred_tools,
                "output_preferences": self.user.output_preferences,
                "common_project_contexts": self.user.common_project_contexts,
                "long_term_constraints": self.user.long_term_constraints,
            },
        }


_PROFILE_CACHE: SessionProfile | None = None


def _read_text_or_default(path: Path, fallback: str) -> str:
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return fallback


def _split_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw in markdown.splitlines():
        line = raw.rstrip("\n")
        match = _HEADER_RE.match(line.strip())
        if match:
            current = match.group(1).strip().lower()
            sections.setdefault(current, [])
            continue
        if not current:
            continue
        sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _section_text(sections: dict[str, str], *aliases: str) -> str:
    for key in aliases:
        text = sections.get(key.strip().lower(), "").strip()
        if text:
            return text
    return ""


def _section_items(sections: dict[str, str], *aliases: str) -> list[str]:
    text = _section_text(sections, *aliases)
    if not text:
        return []
    items: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            item = bullet.group(1).strip()
            if item:
                items.append(item)
            continue
        if ":" in line:
            _, value = line.split(":", 1)
            v = value.strip()
            if v:
                items.append(v)
            continue
        if len(line) > 2 and not line.lower().startswith("when ") and not line.lower().startswith("avoid "):
            items.append(line)
    # keep order while deduping
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _dedupe_list(items: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def _parse_list_value(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    if ";" in text:
        parts = [x.strip() for x in text.split(";")]
    elif "|" in text:
        parts = [x.strip() for x in text.split("|")]
    else:
        parts = [x.strip() for x in text.split(",")]
    return _dedupe_list([x for x in parts if x])


def _extract_override_map(sections: dict[str, str], aliases: tuple[str, ...]) -> dict[str, str]:
    text = _section_text(sections, *aliases)
    if not text:
        return {}
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _KV_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if key and value:
            out[key] = value
    return out


def _normalize_override_values(
    overrides: dict[str, str],
    schema: dict[str, str],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    scalar_values: dict[str, str] = {}
    list_values: dict[str, list[str]] = {}
    for key, raw in overrides.items():
        if key not in schema:
            continue
        mode = schema[key]
        if mode == "list":
            items = _parse_list_value(raw)
            if items:
                list_values[key] = items
            continue
        value = str(raw).strip()
        if value:
            scalar_values[key] = value
    return scalar_values, list_values


def _upsert_top_level_section(markdown: str, *, title: str, aliases: tuple[str, ...], body_lines: list[str]) -> str:
    lines = markdown.splitlines()
    heading_pattern = re.compile(r"^##\s+(.+?)\s*$")
    wanted = {title.strip().lower(), *[x.strip().lower() for x in aliases]}

    start = -1
    for idx, raw in enumerate(lines):
        match = heading_pattern.match(raw.strip())
        if not match:
            continue
        if match.group(1).strip().lower() in wanted:
            start = idx
            break

    if start < 0:
        out = list(lines)
        if out and out[-1].strip():
            out.append("")
        out.append(f"## {title}")
        out.append("")
        out.extend(body_lines)
        out.append("")
        return "\n".join(out).strip() + "\n"

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if heading_pattern.match(lines[idx].strip()):
            end = idx
            break

    out = lines[: start + 1] + [""] + body_lines + [""] + lines[end:]
    return "\n".join(out).strip() + "\n"


def _extract_kv(text: str, key: str, default: str = "") -> str:
    pattern = re.compile(rf"^{re.escape(key)}\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return default
    return match.group(1).strip()


def _parse_soul(markdown: str) -> SoulConfig:
    sections = _split_sections(markdown)
    identity = _section_text(sections, "identity")
    mission_raw = _section_text(sections, "mission")
    mission_items = _section_items(sections, "mission")
    mission = mission_items[0] if mission_items else mission_raw.splitlines()[0].strip() if mission_raw else ""

    core = _section_items(sections, "core principles")
    spatial = _section_items(sections, "spatial reasoning guidelines")
    hierarchy = _section_items(sections, "execution hierarchy")
    data_rules = _section_items(sections, "data handling rules")
    output_std = _section_items(sections, "output standards")
    safety = _section_items(sections, "safety boundaries")
    collab = _section_items(sections, "collaboration philosophy")

    repro = [x for x in (core + data_rules + output_std) if "reproduc" in x.lower() or "trace" in x.lower()]
    truth = [x for x in (core + safety) if any(k in x.lower() for k in ("uncertain", "truth", "fabricat", "assumption"))]
    reasoning = " ".join(core[:2]).strip() or "Prefer structured, reproducible geospatial workflows."

    soul_overrides = _extract_override_map(sections, _SOUL_OVERRIDE_ALIASES)
    soul_override_scalars, soul_override_lists = _normalize_override_values(soul_overrides, _SOUL_OVERRIDE_SCHEMA)
    mission = soul_override_scalars.get("mission", mission)
    reasoning = soul_override_scalars.get("reasoning_philosophy", reasoning)
    spatial = soul_override_lists.get("spatial_reasoning_guidelines", spatial)
    output_std = soul_override_lists.get("output_quality_standards", output_std)
    collab = soul_override_lists.get("collaboration_philosophy", collab)

    return SoulConfig(
        identity=identity,
        mission=mission,
        reasoning_philosophy=reasoning,
        geospatial_principles=core,
        safety_boundaries=safety,
        reproducibility_requirements=repro,
        execution_hierarchy=hierarchy,
        truthfulness_rules=truth,
        output_quality_standards=output_std,
        collaboration_philosophy=collab,
        data_handling_rules=data_rules,
        spatial_reasoning_guidelines=spatial,
        raw_text=markdown,
    )


def _parse_user(markdown: str) -> UserProfile:
    sections = _split_sections(markdown)
    identity = _section_text(sections, "identity")
    role = _extract_kv(identity, "Role", "geospatial analyst")
    domain = _extract_kv(identity, "Domain", "GIS / geospatial data analysis")

    language_sec = _section_text(sections, "language preference")
    preferred_language = _extract_kv(language_sec, "Preferred language", "Chinese or English")

    style_items = _section_items(sections, "communication style")
    preferred_tone = ", ".join(style_items[:3]) if style_items else "concise, structured"

    preferred_tools = _section_items(sections, "tool preferences")
    output_preferences = _section_items(sections, "output preferences")
    reproducibility = _section_items(sections, "reproducibility expectations", "data handling preferences")
    privacy = _section_items(sections, "privacy and safety")
    contexts = _section_items(sections, "common project contexts")
    constraints = _section_items(sections, "long-term constraints and habits")
    habits = _section_items(sections, "collaboration expectations", "technical level")

    user_overrides = _extract_override_map(sections, _USER_OVERRIDE_ALIASES)
    user_override_scalars, user_override_lists = _normalize_override_values(user_overrides, _USER_OVERRIDE_SCHEMA)
    role = user_override_scalars.get("role", role)
    domain = user_override_scalars.get("domain_background", domain)
    preferred_language = user_override_scalars.get("preferred_language", preferred_language)
    preferred_tone = user_override_scalars.get("preferred_tone", preferred_tone)
    preferred_tools = user_override_lists.get("preferred_tools", preferred_tools)
    output_preferences = user_override_lists.get("output_preferences", output_preferences)
    reproducibility = user_override_lists.get("reproducibility_expectations", reproducibility)
    privacy = user_override_lists.get("privacy_preferences", privacy)
    contexts = user_override_lists.get("common_project_contexts", contexts)
    constraints = user_override_lists.get("long_term_constraints", constraints)
    habits = user_override_lists.get("workflow_habits", habits)

    return UserProfile(
        role=role,
        domain_background=domain,
        preferred_language=preferred_language,
        preferred_tone=preferred_tone,
        preferred_tools=preferred_tools,
        output_preferences=output_preferences,
        reproducibility_expectations=reproducibility,
        privacy_preferences=privacy,
        common_project_contexts=contexts,
        long_term_constraints=constraints,
        workflow_habits=habits,
        raw_text=markdown,
    )


def _write_default_if_missing(path: Path, text: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def ensure_profile_layers(workspace_root: Path | None = None) -> dict[str, str]:
    root = (workspace_root or Path.cwd()).resolve()
    home = geoclaw_home()
    home.mkdir(parents=True, exist_ok=True)

    workspace_soul = root / "soul.md"
    workspace_user = root / "user.md"
    home_soul = home / "soul.md"
    home_user = home / "user.md"

    soul_seed = _read_text_or_default(workspace_soul, DEFAULT_SOUL_TEMPLATE)
    user_seed = _read_text_or_default(workspace_user, DEFAULT_USER_TEMPLATE)

    _write_default_if_missing(home_soul, soul_seed)
    _write_default_if_missing(home_user, user_seed)

    return {
        "workspace_root": str(root),
        "workspace_soul": str(workspace_soul),
        "workspace_user": str(workspace_user),
        "home_soul": str(home_soul),
        "home_user": str(home_user),
    }


def _resolve_layer_path(
    *,
    env_key: str,
    preferred_paths: list[Path],
) -> Path:
    env_value = os.environ.get(env_key, "").strip()
    if env_value:
        env_path = Path(env_value).expanduser().resolve()
        if env_path.exists() and env_path.is_file():
            return env_path

    for path in preferred_paths:
        if path.exists() and path.is_file():
            return path.resolve()

    return preferred_paths[0].resolve()


def load_session_profile(workspace_root: Path | None = None, *, force_reload: bool = False) -> SessionProfile:
    global _PROFILE_CACHE
    if _PROFILE_CACHE is not None and not force_reload:
        return _PROFILE_CACHE

    root = (workspace_root or Path.cwd()).resolve()
    ensured = ensure_profile_layers(root)

    soul_path = _resolve_layer_path(
        env_key="GEOCLAW_SOUL_PATH",
        preferred_paths=[
            Path(ensured["home_soul"]),
            Path(ensured["workspace_soul"]),
        ],
    )
    user_path = _resolve_layer_path(
        env_key="GEOCLAW_USER_PATH",
        preferred_paths=[
            Path(ensured["home_user"]),
            Path(ensured["workspace_user"]),
        ],
    )

    soul_text = _read_text_or_default(soul_path, DEFAULT_SOUL_TEMPLATE)
    user_text = _read_text_or_default(user_path, DEFAULT_USER_TEMPLATE)

    profile = SessionProfile(
        soul=_parse_soul(soul_text),
        user=_parse_user(user_text),
        soul_path=str(soul_path),
        user_path=str(user_path),
        loaded_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    _PROFILE_CACHE = profile
    return profile


def apply_dialogue_profile_update(
    *,
    target: str,
    summary: str = "",
    set_values: dict[str, str] | None = None,
    add_values: dict[str, list[str]] | None = None,
    workspace_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    target_clean = str(target or "").strip().lower()
    if target_clean not in {"user", "soul"}:
        raise ValueError("target must be one of: user, soul")

    root = (workspace_root or Path.cwd()).resolve()
    session = load_session_profile(root, force_reload=True)
    file_path = Path(session.user_path if target_clean == "user" else session.soul_path).resolve()
    markdown = _read_text_or_default(file_path, DEFAULT_USER_TEMPLATE if target_clean == "user" else DEFAULT_SOUL_TEMPLATE)
    sections = _split_sections(markdown)

    schema = _USER_OVERRIDE_SCHEMA if target_clean == "user" else _SOUL_OVERRIDE_SCHEMA
    aliases = _USER_OVERRIDE_ALIASES if target_clean == "user" else _SOUL_OVERRIDE_ALIASES
    title = _USER_OVERRIDE_SECTION if target_clean == "user" else _SOUL_OVERRIDE_SECTION
    existing_map = _extract_override_map(sections, aliases)

    set_values = dict(set_values or {})
    add_values = dict(add_values or {})
    blocked_keys: list[str] = []
    ignored_keys: list[str] = []

    merged_scalars, merged_lists = _normalize_override_values(existing_map, schema)

    for raw_key, raw_value in set_values.items():
        key = str(raw_key).strip().lower()
        value = str(raw_value).strip()
        if not key:
            continue
        if target_clean == "soul" and key in _SOUL_LOCKED_KEYS:
            blocked_keys.append(key)
            continue
        if key not in schema:
            ignored_keys.append(key)
            continue
        if schema[key] == "list":
            merged_lists[key] = _parse_list_value(value)
        else:
            merged_scalars[key] = value

    for raw_key, raw_items in add_values.items():
        key = str(raw_key).strip().lower()
        if not key:
            continue
        if target_clean == "soul" and key in _SOUL_LOCKED_KEYS:
            blocked_keys.append(key)
            continue
        if key not in schema:
            ignored_keys.append(key)
            continue
        if schema[key] != "list":
            ignored_keys.append(key)
            continue
        current = list(merged_lists.get(key, []))
        current.extend([str(x).strip() for x in (raw_items or []) if str(x).strip()])
        merged_lists[key] = _dedupe_list(current)

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    body_lines = [f"updated_at: {now}"]
    summary_text = " ".join(summary.split()).strip()
    if summary_text:
        body_lines.append(f"last_summary: {summary_text}")

    for key in sorted(schema.keys()):
        mode = schema[key]
        if mode == "list":
            values = merged_lists.get(key, [])
            if values:
                body_lines.append(f"{key}: {'; '.join(values)}")
        else:
            value = merged_scalars.get(key, "").strip()
            if value:
                body_lines.append(f"{key}: {value}")

    updated_markdown = _upsert_top_level_section(
        markdown,
        title=title,
        aliases=aliases,
        body_lines=body_lines,
    )

    changed = updated_markdown.strip() != markdown.strip()
    if changed and not dry_run:
        file_path.write_text(updated_markdown, encoding="utf-8")

    return {
        "target": target_clean,
        "file": str(file_path),
        "updated_at": now,
        "changed": bool(changed),
        "dry_run": bool(dry_run),
        "blocked_keys": _dedupe_list(blocked_keys),
        "ignored_keys": _dedupe_list(ignored_keys),
        "set_keys": sorted([str(k).strip().lower() for k in set_values.keys() if str(k).strip()]),
        "add_keys": sorted([str(k).strip().lower() for k in add_values.keys() if str(k).strip()]),
    }
