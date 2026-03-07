from __future__ import annotations

import json
from pathlib import Path

from .models import SkillSpec


class SkillRegistry:
    """Loads skill definitions from JSON for extensible orchestration."""

    def __init__(self, registry_path: str | Path) -> None:
        self.registry_path = Path(registry_path)
        self._skills: dict[str, SkillSpec] = {}

    def load(self) -> None:
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        items = payload.get("skills") or []
        skills: dict[str, SkillSpec] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id", "")).strip()
            if not sid:
                continue
            skills[sid] = SkillSpec(
                skill_id=sid,
                skill_type=str(item.get("type", "")).strip(),
                description=str(item.get("description", "")).strip(),
                pipeline=str(item.get("pipeline", "")).strip(),
                requires_osm=bool(item.get("requires_osm", False)),
                default_bbox=str(item.get("default_bbox", "")).strip(),
                report_path=str(item.get("report_path", "")).strip(),
                pre_steps=[str(x) for x in (item.get("pre_steps") or [])],
                system_prompt=str(item.get("system_prompt", "")).strip(),
            )
        self._skills = skills

    def get(self, skill_id: str) -> SkillSpec:
        if not self._skills:
            self.load()
        if skill_id not in self._skills:
            raise KeyError(f"skill not found: {skill_id}")
        return self._skills[skill_id]

    def list(self) -> list[SkillSpec]:
        if not self._skills:
            self.load()
        return list(self._skills.values())
