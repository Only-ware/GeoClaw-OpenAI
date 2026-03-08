from __future__ import annotations

import copy
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_METHOD_TEMPLATES: dict[str, list[str]] = {
    "proximity_analysis": [
        "buffer",
        "multi_ring_buffer",
        "distance_to_nearest",
        "spatial_join_by_distance",
    ],
    "accessibility_analysis": [
        "service_area",
        "travel_time_catchment",
        "network_reachability",
    ],
    "site_selection": [
        "weighted_overlay",
        "location_allocation",
        "constrained_candidate_filtering",
    ],
    "change_detection": [
        "raster_differencing",
        "temporal_overlay",
        "trend_analysis",
    ],
    "trajectory_analysis": [
        "od_extraction",
        "staypoint_detection",
        "trip_segmentation",
        "flow_aggregation",
    ],
    "spatial_comparison": [
        "zonal_summary",
        "rank_and_compare",
    ],
}

_DEFAULT_RULE_CONFIG: dict[str, Any] = {
    "keywords": {
        "distance": ["buffer", "distance", "距离", "area", "面积", "半径", "周边"],
        "area": ["area", "面积"],
        "scale": ["maup", "尺度", "scale"],
        "causal": ["因果", "causal", "effect", "impact", "导致", "原因", "机制"],
        "exploratory": ["探索", "exploratory", "描述", "pattern", "趋势", "分布", "对比"],
    },
    "crs": {
        "geographic": ["EPSG:4326", "EPSG:4490"],
    },
    "geometry_rules": {
        "non_polygon_for_area_metric": [
            "point",
            "multipoint",
            "line",
            "multiline",
            "linestring",
            "multilinestring",
        ],
    },
    "dataset_type_rules": {
        "trajectory_required": ["trajectory", "network"],
        "accessibility_preferred": ["network", "trajectory"],
    },
    "temporal_rules": {
        "change_detection_min_slices": 2,
    },
    "constraints": {
        "distance_requires_projected_crs": "reproject_to_projected_crs_before_distance_ops",
        "unify_crs_before_overlay": "unify_crs_before_overlay",
        "ensure_extent_overlap": "ensure_extent_overlap",
        "change_detection_requires_multiple_time_slices": "change_detection_requires_multiple_time_slices",
        "trajectory_requires_data": "trajectory_task_requires_trajectory_or_network_data",
        "readonly_inputs": "do_not_overwrite_input",
        "workspace_output_only": "workspace_output_only",
        "registered_tools_only": "registered_tools_only",
    },
    "warnings": {
        "single_dataset": "single_dataset_context_may_limit_spatial_relationship_analysis",
        "missing_extent": "missing_extent_metadata_on_some_datasets",
        "extent_non_overlap": "dataset_extent_non_overlap",
        "no_datasets": "no_datasets_attached_to_reasoning_input",
        "insufficient_temporal_slices": "insufficient_temporal_slices_for_change_detection",
        "accessibility_prefers_network": "accessibility_analysis_prefers_network_data",
        "area_metric_non_polygon": "area_metric_with_non_polygon_geometry",
        "maup_scale": "maup_or_scale_effects_should_be_reported",
        "causal_requires_design": "causal_claim_requires_identification_strategy",
        "causal_without_design": "causal_inference_without_identification_design",
        "missing_sensitivity_hints": "parameter_sensitivity_hints_missing",
        "scale_not_explained": "scale_effects_not_explained_in_limitations",
    },
}

_RULE_FILE_ORDER = [
    "crs_rules.yaml",
    "topology_rules.yaml",
    "temporal_rules.yaml",
    "scale_rules.yaml",
    "safety_rules.yaml",
]

_TEMPLATE_FILE_BY_TASK = {
    "proximity_analysis": "proximity.yaml",
    "accessibility_analysis": "accessibility.yaml",
    "site_selection": "site_selection.yaml",
    "change_detection": "change_detection.yaml",
    "trajectory_analysis": "trajectory.yaml",
    "spatial_comparison": "spatial_comparison.yaml",
}

_DEFAULT_REASONER_TEMPLATE: dict[str, Any] = {
    "system_prompt": (
        "You are GeoClaw Spatial Reasoning Engine. "
        "Return ONLY one JSON object, no markdown and no extra text. "
        "Respect hard constraints and preserve reproducibility."
    ),
    "user_instruction": (
        "Given query/rules/baseline, return a structured geospatial reasoning JSON "
        "that follows output_schema exactly."
    ),
    "output_schema": {
        "required": [
            "recommended_analysis_strategy",
            "reasoning_mode",
            "reasoning",
            "assumptions",
            "limitations",
            "uncertainty_level",
            "uncertainty_score",
        ],
        "recommended_analysis_strategy_required": ["primary_method", "secondary_methods"],
        "reasoning_mode_values": ["exploratory", "causal_inference"],
        "uncertainty_level_values": ["low", "medium", "high"],
        "max_secondary_methods": 3,
    },
}


def _default_rules_dir() -> Path:
    return Path(__file__).resolve().parent / "rules"


def _default_templates_dir() -> Path:
    return Path(__file__).resolve().parent / "templates"


def _resolve_dir(explicit_dir: str, *, env_var: str, default_dir: Path) -> Path:
    if explicit_dir.strip():
        return Path(explicit_dir).expanduser().resolve()
    env_path = os.environ.get(env_var, "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return default_dir.resolve()


def _read_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"YAML root must be mapping: {path}")
    return raw


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _as_str_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
        raise ValueError(f"{field} must be a non-empty string list")
    return [str(x).strip() for x in value]


def _validate_mapping_str(value: Any, *, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    out: dict[str, str] = {}
    for k, v in value.items():
        if not isinstance(k, str) or not isinstance(v, str) or not k.strip() or not v.strip():
            raise ValueError(f"{field} must only contain non-empty string key/value pairs")
        out[k.strip()] = v.strip()
    return out


def _validate_templates(catalog: dict[str, list[str]]) -> dict[str, list[str]]:
    validated: dict[str, list[str]] = {}
    for task, methods in catalog.items():
        if not isinstance(task, str) or not task.strip():
            raise ValueError("template task key must be a non-empty string")
        validated[task.strip()] = _as_str_list(methods, field=f"templates.{task}")
    return validated


def _validate_rule_config(config: dict[str, Any]) -> dict[str, Any]:
    keywords = config.get("keywords", {})
    if not isinstance(keywords, dict):
        raise ValueError("rules.keywords must be a mapping")

    crs = config.get("crs", {})
    if not isinstance(crs, dict):
        raise ValueError("rules.crs must be a mapping")

    geometry_rules = config.get("geometry_rules", {})
    if not isinstance(geometry_rules, dict):
        raise ValueError("rules.geometry_rules must be a mapping")

    dataset_type_rules = config.get("dataset_type_rules", {})
    if not isinstance(dataset_type_rules, dict):
        raise ValueError("rules.dataset_type_rules must be a mapping")

    temporal_rules = config.get("temporal_rules", {})
    if not isinstance(temporal_rules, dict):
        raise ValueError("rules.temporal_rules must be a mapping")

    validated = copy.deepcopy(config)
    validated["keywords"] = {
        "distance": _as_str_list(keywords.get("distance", []), field="rules.keywords.distance"),
        "area": _as_str_list(keywords.get("area", []), field="rules.keywords.area"),
        "scale": _as_str_list(keywords.get("scale", []), field="rules.keywords.scale"),
        "causal": _as_str_list(keywords.get("causal", []), field="rules.keywords.causal"),
        "exploratory": _as_str_list(keywords.get("exploratory", []), field="rules.keywords.exploratory"),
    }
    validated["crs"] = {
        "geographic": _as_str_list(crs.get("geographic", []), field="rules.crs.geographic"),
    }
    validated["geometry_rules"] = {
        "non_polygon_for_area_metric": _as_str_list(
            geometry_rules.get("non_polygon_for_area_metric", []),
            field="rules.geometry_rules.non_polygon_for_area_metric",
        )
    }
    validated["dataset_type_rules"] = {
        "trajectory_required": _as_str_list(
            dataset_type_rules.get("trajectory_required", []),
            field="rules.dataset_type_rules.trajectory_required",
        ),
        "accessibility_preferred": _as_str_list(
            dataset_type_rules.get("accessibility_preferred", []),
            field="rules.dataset_type_rules.accessibility_preferred",
        ),
    }

    min_slices = temporal_rules.get("change_detection_min_slices", 0)
    if not isinstance(min_slices, int) or min_slices < 1:
        raise ValueError("rules.temporal_rules.change_detection_min_slices must be >= 1")
    validated["temporal_rules"] = {"change_detection_min_slices": min_slices}

    validated["constraints"] = _validate_mapping_str(config.get("constraints", {}), field="rules.constraints")
    validated["warnings"] = _validate_mapping_str(config.get("warnings", {}), field="rules.warnings")
    return validated


def _validate_reasoner_template(config: dict[str, Any]) -> dict[str, Any]:
    system_prompt = str(config.get("system_prompt", "")).strip()
    user_instruction = str(config.get("user_instruction", "")).strip()
    schema = config.get("output_schema", {})
    if not isinstance(schema, dict):
        raise ValueError("reasoner template output_schema must be mapping")
    if not system_prompt:
        raise ValueError("reasoner template system_prompt is required")
    if not user_instruction:
        raise ValueError("reasoner template user_instruction is required")

    required = _as_str_list(schema.get("required", []), field="reasoner.output_schema.required")
    strat_required = _as_str_list(
        schema.get("recommended_analysis_strategy_required", []),
        field="reasoner.output_schema.recommended_analysis_strategy_required",
    )
    mode_values = _as_str_list(
        schema.get("reasoning_mode_values", []),
        field="reasoner.output_schema.reasoning_mode_values",
    )
    uncertainty_values = _as_str_list(
        schema.get("uncertainty_level_values", []),
        field="reasoner.output_schema.uncertainty_level_values",
    )
    max_secondary = schema.get("max_secondary_methods", 3)
    if not isinstance(max_secondary, int) or max_secondary < 1:
        raise ValueError("reasoner.output_schema.max_secondary_methods must be >= 1")

    return {
        "system_prompt": system_prompt,
        "user_instruction": user_instruction,
        "output_schema": {
            "required": required,
            "recommended_analysis_strategy_required": strat_required,
            "reasoning_mode_values": mode_values,
            "uncertainty_level_values": uncertainty_values,
            "max_secondary_methods": max_secondary,
        },
    }


def _load_template_yaml_for_task(*, task: str, path: Path) -> list[str]:
    payload = _read_yaml(path)
    methods = payload.get("methods")
    if methods is None:
        raise ValueError(f"Missing methods field in template file: {path}")
    if "task_type" in payload and str(payload.get("task_type", "")).strip() not in {"", task}:
        raise ValueError(f"Template task_type mismatch in file: {path}")
    return _as_str_list(methods, field=f"template.{task}.methods")


@lru_cache(maxsize=16)
def _load_reasoner_template_cached(templates_dir: str, strict: bool) -> dict[str, Any]:
    resolved_dir = Path(templates_dir)
    base_cfg = copy.deepcopy(_DEFAULT_REASONER_TEMPLATE)
    path = resolved_dir / "llm_reasoner.yaml"

    if not resolved_dir.exists():
        if strict:
            raise FileNotFoundError(f"templates directory not found: {resolved_dir}")
        return _validate_reasoner_template(base_cfg)

    if path.exists():
        try:
            raw = _read_yaml(path)
            merged = _deep_merge(base_cfg, raw)
            return _validate_reasoner_template(merged)
        except Exception:
            if strict:
                raise
            # Non-strict mode should tolerate broken template and fallback to defaults.
            return _validate_reasoner_template(base_cfg)
    elif strict:
        raise FileNotFoundError(f"reasoner template not found: {path}")
    return _validate_reasoner_template(base_cfg)


@lru_cache(maxsize=16)
def _load_method_templates_cached(templates_dir: str, strict: bool) -> dict[str, list[str]]:
    resolved_dir = Path(templates_dir)
    catalog = copy.deepcopy(_DEFAULT_METHOD_TEMPLATES)

    if not resolved_dir.exists():
        if strict:
            raise FileNotFoundError(f"templates directory not found: {resolved_dir}")
        return _validate_templates(catalog)

    for task, filename in _TEMPLATE_FILE_BY_TASK.items():
        path = resolved_dir / filename
        if not path.exists():
            continue
        try:
            catalog[task] = _load_template_yaml_for_task(task=task, path=path)
        except Exception:
            if strict:
                raise
            continue
    return _validate_templates(catalog)


@lru_cache(maxsize=16)
def _load_rule_config_cached(rules_dir: str, strict: bool) -> dict[str, Any]:
    resolved_dir = Path(rules_dir)
    config = copy.deepcopy(_DEFAULT_RULE_CONFIG)

    if not resolved_dir.exists():
        if strict:
            raise FileNotFoundError(f"rules directory not found: {resolved_dir}")
        return _validate_rule_config(config)

    for filename in _RULE_FILE_ORDER:
        path = resolved_dir / filename
        if not path.exists():
            continue
        try:
            config = _deep_merge(config, _read_yaml(path))
        except Exception:
            if strict:
                raise
            continue
    return _validate_rule_config(config)


def load_method_templates(*, templates_dir: str = "", strict: bool = False) -> dict[str, list[str]]:
    resolved = _resolve_dir(
        templates_dir,
        env_var="GEOCLAW_SRE_TEMPLATES_DIR",
        default_dir=_default_templates_dir(),
    )
    return _load_method_templates_cached(str(resolved), strict)


def load_rule_config(*, rules_dir: str = "", strict: bool = False) -> dict[str, Any]:
    resolved = _resolve_dir(
        rules_dir,
        env_var="GEOCLAW_SRE_RULES_DIR",
        default_dir=_default_rules_dir(),
    )
    return _load_rule_config_cached(str(resolved), strict)


def load_reasoner_template(*, templates_dir: str = "", strict: bool = False) -> dict[str, Any]:
    resolved = _resolve_dir(
        templates_dir,
        env_var="GEOCLAW_SRE_TEMPLATES_DIR",
        default_dir=_default_templates_dir(),
    )
    return _load_reasoner_template_cached(str(resolved), strict)


def clear_sre_config_cache() -> None:
    _load_method_templates_cached.cache_clear()
    _load_rule_config_cached.cache_clear()
    _load_reasoner_template_cached.cache_clear()


__all__ = [
    "clear_sre_config_cache",
    "load_method_templates",
    "load_reasoner_template",
    "load_rule_config",
]
