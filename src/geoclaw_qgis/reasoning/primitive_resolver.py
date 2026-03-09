from __future__ import annotations

from typing import Any

from .schemas import ReasoningInput


def resolve_geo_primitives(input_data: ReasoningInput) -> dict[str, Any]:
    entities: list[str] = []
    relations: list[str] = []
    metrics: list[str] = []

    for ds in input_data.datasets:
        if ds.geometry:
            entities.append(ds.geometry)
        if ds.dataset_type:
            entities.append(ds.dataset_type)

    text = input_data.query.lower()
    if any(x in text for x in ("within", "buffer", "距离", "周边", "邻近")):
        relations.append("within_distance")
    if any(x in text for x in ("join", "叠加", "intersect", "覆盖")):
        relations.append("intersects")
    if any(x in text for x in ("nearest", "最近", "可达", "reach")):
        relations.append("nearest")

    if any(x in text for x in ("count", "数量", "统计")):
        metrics.append("count")
    if any(x in text for x in ("density", "密度")):
        metrics.append("density")
    if any(x in text for x in ("diversity", "多样性", "公平")):
        metrics.append("diversity")

    return {
        "entities": sorted(set(entities)),
        "spatial_relations": sorted(set(relations)),
        "target_metrics": sorted(set(metrics)),
    }
