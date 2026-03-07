from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepSpec:
    """Pipeline step declaration."""

    step_id: str
    algorithm: str
    params: dict[str, Any] = field(default_factory=dict)
    needs: list[str] = field(default_factory=list)


@dataclass
class StepResult:
    step_id: str
    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    message: str = ""
