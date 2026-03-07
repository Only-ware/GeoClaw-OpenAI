from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextCompressionResult:
    text: str
    compressed: bool
    original_chars: int
    output_chars: int


def compress_context(text: str, *, max_chars: int = 12000) -> ContextCompressionResult:
    raw = text or ""
    src = raw.strip()
    src_len = len(src)
    if max_chars <= 0 or src_len <= max_chars:
        return ContextCompressionResult(
            text=src,
            compressed=False,
            original_chars=src_len,
            output_chars=src_len,
        )

    head_chars = max(200, int(max_chars * 0.45))
    tail_chars = max(120, int(max_chars * 0.2))
    reserve_chars = 220
    middle_budget = max(120, max_chars - head_chars - tail_chars - reserve_chars)

    head = src[:head_chars].strip()
    tail = src[-tail_chars:].strip()

    lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
    keywords = (
        "summary",
        "risk",
        "warning",
        "error",
        "score",
        "site",
        "location",
        "network",
        "od",
        "结论",
        "建议",
        "风险",
        "错误",
        "评分",
        "选址",
        "区位",
        "轨迹",
    )

    selected: list[str] = []
    used = 0
    for line in lines:
        lowered = line.lower()
        if any(k in lowered for k in keywords):
            selected.append(line)
            used += len(line) + 1
            if used >= middle_budget:
                break

    if not selected:
        center = src_len // 2
        span = min(middle_budget, max(120, src_len // 6))
        mid_raw = src[max(0, center - span // 2) : min(src_len, center + span // 2)]
        selected = [mid_raw.strip()]

    middle = "\n".join(selected).strip()
    banner = (
        f"[Context compressed | original={src_len} chars | target<={max_chars} chars]\n"
        "[Head]\n"
    )
    merged = (
        f"{banner}{head}\n"
        "[Key Excerpts]\n"
        f"{middle}\n"
        "[Tail]\n"
        f"{tail}"
    ).strip()

    if len(merged) > max_chars:
        merged = merged[:max_chars].rstrip()

    return ContextCompressionResult(
        text=merged,
        compressed=True,
        original_chars=src_len,
        output_chars=len(merged),
    )
