from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from geoclaw_qgis.core.models import StepResult
from geoclaw_qgis.providers.qgis_process_runner import QgisProcessRunner


def _merged_params(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if value is not None:
            merged[key] = value
    return merged


@dataclass
class VectorAnalysisService:
    """Reusable vector operation wrappers with flexible parameter overrides."""

    runner: QgisProcessRunner

    def run_custom(self, algorithm: str, params: dict[str, Any], step_id: str = "vector_custom") -> StepResult:
        return self.runner.run_algorithm(algorithm=algorithm, params=params, step_id=step_id)

    def reproject(
        self,
        input_path: str,
        target_crs: str,
        output_path: str,
        step_id: str = "vector_reproject",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_path,
            "TARGET_CRS": target_crs,
            "OUTPUT": output_path,
        }
        return self.run_custom("native:reprojectlayer", _merged_params(base, extra_params), step_id=step_id)

    def buffer(
        self,
        input_path: str,
        distance: float,
        output_path: str,
        step_id: str = "vector_buffer",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_path,
            "DISTANCE": distance,
            "SEGMENTS": 12,
            "END_CAP_STYLE": 0,
            "JOIN_STYLE": 0,
            "MITER_LIMIT": 2,
            "DISSOLVE": 0,
            "SEPARATE_DISJOINT": 0,
            "OUTPUT": output_path,
        }
        return self.run_custom("native:buffer", _merged_params(base, extra_params), step_id=step_id)

    def clip(
        self,
        input_path: str,
        overlay_path: str,
        output_path: str,
        step_id: str = "vector_clip",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_path,
            "OVERLAY": overlay_path,
            "OUTPUT": output_path,
        }
        return self.run_custom("native:clip", _merged_params(base, extra_params), step_id=step_id)

    def dissolve(
        self,
        input_path: str,
        output_path: str,
        fields: list[str] | None = None,
        step_id: str = "vector_dissolve",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_path,
            "FIELD": fields or [],
            "SEPARATE_DISJOINT": 0,
            "OUTPUT": output_path,
        }
        return self.run_custom("native:dissolve", _merged_params(base, extra_params), step_id=step_id)

    def intersection(
        self,
        input_path: str,
        overlay_path: str,
        output_path: str,
        step_id: str = "vector_intersection",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_path,
            "OVERLAY": overlay_path,
            "INPUT_FIELDS": [],
            "OVERLAY_FIELDS": [],
            "OVERLAY_FIELDS_PREFIX": "",
            "OUTPUT": output_path,
        }
        return self.run_custom("native:intersection", _merged_params(base, extra_params), step_id=step_id)

    def extract_by_expression(
        self,
        input_path: str,
        expression: str,
        output_path: str,
        step_id: str = "vector_extract_expression",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_path,
            "EXPRESSION": expression,
            "OUTPUT": output_path,
        }
        return self.run_custom("native:extractbyexpression", _merged_params(base, extra_params), step_id=step_id)

    def field_calculator(
        self,
        input_path: str,
        field_name: str,
        field_type: int,
        field_length: int,
        field_precision: int,
        formula: str,
        output_path: str,
        step_id: str = "vector_field_calculator",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_path,
            "FIELD_NAME": field_name,
            "FIELD_TYPE": field_type,
            "FIELD_LENGTH": field_length,
            "FIELD_PRECISION": field_precision,
            "FORMULA": formula,
            "OUTPUT": output_path,
        }
        return self.run_custom("native:fieldcalculator", _merged_params(base, extra_params), step_id=step_id)

