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
class RasterAnalysisService:
    """Reusable raster operation wrappers with flexible parameter overrides."""

    runner: QgisProcessRunner

    def run_custom(self, algorithm: str, params: dict[str, Any], step_id: str = "raster_custom") -> StepResult:
        return self.runner.run_algorithm(algorithm=algorithm, params=params, step_id=step_id)

    def heatmap_from_points(
        self,
        input_points: str,
        output_raster: str,
        radius: float = 3000,
        pixel_size: float = 200,
        step_id: str = "raster_heatmap",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_points,
            "RADIUS": radius,
            "PIXEL_SIZE": pixel_size,
            "KERNEL": 0,
            "OUTPUT_VALUE": 0,
            "OUTPUT": output_raster,
        }
        return self.run_custom("qgis:heatmapkerneldensityestimation", _merged_params(base, extra_params), step_id)

    def reproject_raster(
        self,
        input_raster: str,
        target_crs: str,
        output_raster: str,
        step_id: str = "raster_reproject",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_raster,
            "TARGET_CRS": target_crs,
            "RESAMPLING": 0,
            "NODATA": None,
            "DATA_TYPE": 0,
            "OUTPUT": output_raster,
        }
        return self.run_custom("gdal:warpreproject", _merged_params(base, extra_params), step_id)

    def clip_by_mask(
        self,
        input_raster: str,
        mask_layer: str,
        output_raster: str,
        step_id: str = "raster_clip_mask",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_raster,
            "MASK": mask_layer,
            "SOURCE_CRS": None,
            "TARGET_CRS": None,
            "CROP_TO_CUTLINE": True,
            "KEEP_RESOLUTION": True,
            "OUTPUT": output_raster,
        }
        return self.run_custom("gdal:cliprasterbymasklayer", _merged_params(base, extra_params), step_id)

    def zonal_statistics(
        self,
        input_polygons: str,
        input_raster: str,
        output_path: str,
        band: int = 1,
        column_prefix: str = "ZS_",
        stats: int | list[int] = 2,
        step_id: str = "raster_zonal_stats",
        **extra_params: Any,
    ) -> StepResult:
        base = {
            "INPUT": input_polygons,
            "INPUT_RASTER": input_raster,
            "RASTER_BAND": band,
            "COLUMN_PREFIX": column_prefix,
            "STATISTICS": stats,
            "OUTPUT": output_path,
        }
        return self.run_custom("native:zonalstatisticsfb", _merged_params(base, extra_params), step_id)

