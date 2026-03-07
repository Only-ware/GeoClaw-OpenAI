from __future__ import annotations

from dataclasses import dataclass, field

from .models import StepResult, StepSpec


@dataclass
class Pipeline:
    """Simple sequential pipeline; DAG scheduling will be added later."""

    steps: list[StepSpec] = field(default_factory=list)

    def add_step(self, step: StepSpec) -> None:
        self.steps.append(step)

    def run(self, runner) -> list[StepResult]:
        results: list[StepResult] = []
        for step in self.steps:
            results.append(runner.run_step(step))
            if not results[-1].success:
                break
        return results
