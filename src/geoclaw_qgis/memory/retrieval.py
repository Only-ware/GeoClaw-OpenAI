from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text or "")]


def text_to_vector(text: str, *, dim: int = 384) -> dict[int, float]:
    tokens = tokenize(text)
    if not tokens:
        return {}
    counts: dict[int, float] = {}
    for tok in tokens:
        h = hashlib.md5(tok.encode("utf-8")).hexdigest()
        idx = int(h[:8], 16) % dim
        sign = 1.0 if (int(h[8:10], 16) % 2 == 0) else -1.0
        counts[idx] = counts.get(idx, 0.0) + sign
    norm = math.sqrt(sum(v * v for v in counts.values()))
    if norm <= 0:
        return {}
    return {k: v / norm for k, v in counts.items()}


def cosine_similarity(vec_a: dict[int, float], vec_b: dict[int, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a
    score = 0.0
    for idx, val in vec_a.items():
        score += val * vec_b.get(idx, 0.0)
    return float(score)


def best_matches(
    query: str,
    items: Iterable[dict[str, object]],
    *,
    top_k: int = 5,
    min_score: float = 0.15,
) -> list[dict[str, object]]:
    qv = text_to_vector(query)
    ranked: list[dict[str, object]] = []
    for item in items:
        text = str(item.get("search_text", "")).strip()
        if not text:
            continue
        sv = text_to_vector(text)
        score = cosine_similarity(qv, sv)
        if score < min_score:
            continue
        row = dict(item)
        row["score"] = round(score, 4)
        ranked.append(row)
    ranked.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    return ranked[: max(1, top_k)]
