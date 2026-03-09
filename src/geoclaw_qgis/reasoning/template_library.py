from __future__ import annotations

from .config_loader import load_method_templates


def methods_for(task_type: str) -> list[str]:
    return list(load_method_templates().get(task_type, []))
