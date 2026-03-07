from __future__ import annotations

import json
import subprocess
from typing import Any

from geoclaw_qgis.core.models import StepResult, StepSpec


class QgisProcessRunner:
    """Execute QGIS processing algorithms through qgis_process CLI."""

    def __init__(self, command: str = "qgis_process") -> None:
        self.command = command

    @staticmethod
    def encode_value(value: Any) -> str:
        if isinstance(value, bool):
            return "1" if value else "0"
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (list, tuple)):
            return ";".join(QgisProcessRunner.encode_value(v) for v in value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def run_algorithm(self, algorithm: str, params: dict[str, Any], step_id: str = "adhoc") -> StepResult:
        args = [self.command, "--json", "run", algorithm, "--"]
        for key, value in params.items():
            args.append(f"{key}={self.encode_value(value)}")

        try:
            proc = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            return StepResult(step_id=step_id, success=False, message=str(exc))

        if proc.returncode != 0:
            return StepResult(
                step_id=step_id,
                success=False,
                message=proc.stderr.strip() or proc.stdout.strip(),
            )

        outputs: dict[str, Any] = {}
        stdout = proc.stdout.strip()
        if stdout:
            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, dict) and "results" in parsed:
                    outputs = parsed.get("results") or {}
                elif isinstance(parsed, dict):
                    outputs = parsed
                else:
                    outputs = {"raw": parsed}
            except json.JSONDecodeError:
                outputs = {"raw": stdout}

        return StepResult(step_id=step_id, success=True, outputs=outputs)

    def run_step(self, step: StepSpec) -> StepResult:
        return self.run_algorithm(step.algorithm, step.params, step_id=step.step_id)
