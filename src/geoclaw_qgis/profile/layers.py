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
