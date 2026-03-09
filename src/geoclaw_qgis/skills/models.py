from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillSpec:
    skill_id: str
    skill_type: str
    description: str = ""
    pipeline: str = ""
    builtin: list[str] = field(default_factory=list)
    default_args: list[str] = field(default_factory=list)
    requires_osm: bool = False
    default_bbox: str = ""
    report_path: str = ""
    pre_steps: list[str] = field(default_factory=list)
    system_prompt: str = ""
