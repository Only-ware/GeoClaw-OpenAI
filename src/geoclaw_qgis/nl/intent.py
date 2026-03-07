from __future__ import annotations

from dataclasses import dataclass
import re


BBOX_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)"
)
TOPN_RE = re.compile(r"(?:top\s*[-_ ]?n|前)\s*(\d{1,4})", re.IGNORECASE)
PATH_HINT_RE = re.compile(r"([~./\\A-Za-z0-9_\-]+/[A-Za-z0-9_\-./\\]+)")
CITY_EXPLICIT_RE = re.compile(r"(?:city|城市)\s*[:：]?\s*([A-Za-z\u4e00-\u9fff]{2,20})", re.IGNORECASE)
CITY_CN_RE = re.compile(r"(?:^|[^\u4e00-\u9fff])([\u4e00-\u9fff]{2,12}市)(?:[^\u4e00-\u9fff]|$)")


@dataclass
class NLPlan:
    query: str
    intent: str
    confidence: float
    reasons: list[str]
    cli_args: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "intent": self.intent,
            "confidence": round(float(self.confidence), 3),
            "reasons": self.reasons,
            "cli_args": self.cli_args,
        }


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(t in text for t in terms)


def _detect_bbox(text: str) -> str:
    m = BBOX_RE.search(text)
    if not m:
        return ""
    vals = [m.group(i).strip() for i in range(1, 5)]
    return ",".join(vals)


def _detect_top_n(text: str) -> int | None:
    m = TOPN_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _detect_data_dir(text: str) -> str:
    if not _contains_any(text.lower(), ("data-dir", "data dir", "本地数据", "数据目录", "本地目录", "目录")):
        return ""
    m = PATH_HINT_RE.search(text)
    if not m:
        return ""
    return m.group(1).strip()


def _detect_city(text: str, text_lower: str) -> str:
    def _normalize_city_name(raw_city: str) -> str:
        city = raw_city.strip()
        # Remove frequent leading function words in Chinese prompts.
        while len(city) > 2 and city[:1] in {"用", "在", "按", "对", "给"}:
            city = city[1:]
        return city

    m = CITY_EXPLICIT_RE.search(text)
    if m:
        city = _normalize_city_name(m.group(1))
        if city and city.endswith("市"):
            return city
        if city:
            return f"{city}市" if re.search(r"[\u4e00-\u9fff]", city) else city

    m2 = CITY_CN_RE.search(text)
    if m2:
        return _normalize_city_name(m2.group(1))

    if "武汉" in text:
        return "武汉市"
    if "beijing" in text_lower:
        return "Beijing"
    if "shanghai" in text_lower:
        return "Shanghai"
    if "guangzhou" in text_lower:
        return "Guangzhou"
    if "shenzhen" in text_lower:
        return "Shenzhen"
    return ""


def _detect_case(text: str, text_lower: str) -> str:
    if _contains_any(text, ("选址", "候选点", "site")):
        return "site_selection"
    if _contains_any(text, ("区位", "location")):
        return "location_analysis"
    if _contains_any(text, ("综合", "advanced", "cluster", "聚类")):
        return "wuhan_advanced"
    if _contains_any(text_lower, ("native", "原生")):
        return "native_cases"
    if _contains_any(text, ("地图", "出图", "制图")):
        return "wuhan_advanced"
    return "native_cases"


def _build_update_plan(query: str, text_lower: str) -> NLPlan:
    reasons = ["Detected update-related keywords."]
    cli_args = ["update"]
    if _contains_any(text_lower, ("检查", "check", "是否有更新", "有没有更新", "只检查", "仅检查")):
        cli_args.append("--check-only")
        reasons.append("Using check-only mode.")
    return NLPlan(query=query, intent="update", confidence=0.97, reasons=reasons, cli_args=cli_args)


def _build_memory_plan(query: str, text: str, text_lower: str) -> NLPlan:
    reasons = ["Detected memory-related keywords."]
    if _contains_any(text_lower, ("long", "长期")):
        cli_args = ["memory", "long"]
        reasons.append("Targeting long-term memory.")
    elif _contains_any(text_lower, ("short", "短期", "最近任务")):
        cli_args = ["memory", "short"]
        reasons.append("Targeting short-term memory.")
    else:
        cli_args = ["memory", "status"]
        reasons.append("Using memory status view.")
    return NLPlan(query=query, intent="memory", confidence=0.95, reasons=reasons, cli_args=cli_args)


def _build_skill_plan(query: str, text: str, text_lower: str) -> NLPlan:
    reasons = ["Detected skill-related keywords."]
    if _contains_any(text_lower, ("list", "列表", "有哪些")):
        return NLPlan(
            query=query,
            intent="skill",
            confidence=0.93,
            reasons=reasons + ["Listing skills."],
            cli_args=["skill", "--", "--list"],
        )

    skill_id = "location_analysis"
    if _contains_any(text, ("选址", "site")):
        skill_id = "site_selection"
    elif _contains_any(text, ("规划", "总结", "ai")):
        skill_id = "ai_planning_assistant"
    reasons.append(f"Resolved skill_id={skill_id}.")
    cli_args = ["skill", "--", "--skill", skill_id]
    if _contains_any(text, ("with ai", "AI总结", "ai总结")) and skill_id != "ai_planning_assistant":
        cli_args.append("--with-ai")
    return NLPlan(query=query, intent="skill", confidence=0.9, reasons=reasons, cli_args=cli_args)


def _build_operator_plan(query: str, text: str, text_lower: str) -> NLPlan:
    reasons = ["Detected operator/single-algorithm keywords."]
    distance = 800
    dist_m = re.search(r"(\d{2,6})\s*(?:m|米)", text_lower)
    if dist_m:
        distance = int(dist_m.group(1))
        reasons.append(f"Detected buffer distance={distance}.")

    output = "data/outputs/nl/operator_buffer.gpkg"
    in_path = "data/raw/wuhan_osm/hospitals.geojson"

    paths = PATH_HINT_RE.findall(text)
    if len(paths) >= 1:
        in_path = paths[0]
        reasons.append(f"Detected input path={in_path}.")
    if len(paths) >= 2:
        output = paths[1]
        reasons.append(f"Detected output path={output}.")

    cli_args = [
        "operator",
        "--algorithm",
        "native:buffer",
        "--param",
        f"INPUT={in_path}",
        "--param-json",
        f"DISTANCE={distance}",
        "--param-json",
        "SEGMENTS=12",
        "--param-json",
        "END_CAP_STYLE=0",
        "--param-json",
        "JOIN_STYLE=0",
        "--param-json",
        "MITER_LIMIT=2",
        "--param-json",
        "DISSOLVE=1",
        "--param-json",
        "SEPARATE_DISJOINT=0",
        "--param",
        f"OUTPUT={output}",
    ]
    return NLPlan(query=query, intent="operator", confidence=0.85, reasons=reasons, cli_args=cli_args)


def _build_run_plan(query: str, text: str, text_lower: str) -> NLPlan:
    case = _detect_case(text, text_lower)
    cli_args = ["run", "--case", case]
    reasons = [f"Resolved case={case}."]

    data_dir = _detect_data_dir(text)
    bbox = _detect_bbox(text)
    city = _detect_city(text, text_lower)

    if data_dir:
        cli_args.extend(["--data-dir", data_dir, "--skip-download"])
        reasons.append(f"Resolved data-dir={data_dir}.")
    elif bbox:
        cli_args.extend(["--bbox", bbox])
        reasons.append(f"Resolved bbox={bbox}.")
    elif city:
        cli_args.extend(["--city", city])
        reasons.append(f"Resolved city={city}.")
    else:
        reasons.append("No explicit input source found; fallback to default runtime bbox/cached data.")

    top_n = _detect_top_n(text)
    if top_n is not None:
        cli_args.extend(["--top-n", str(top_n)])
        reasons.append(f"Resolved top-n={top_n}.")

    if _contains_any(text, ("出图", "地图", "map", "with maps")):
        cli_args.append("--with-maps")
        reasons.append("Enabled map export.")
    if _contains_any(text, ("跳过下载", "skip download", "缓存")):
        if "--skip-download" not in cli_args:
            cli_args.append("--skip-download")
        reasons.append("Enabled skip-download.")
    if _contains_any(text, ("强制下载", "force download", "重新下载")):
        cli_args.append("--force-download")
        reasons.append("Enabled force-download.")

    return NLPlan(query=query, intent="run", confidence=0.82, reasons=reasons, cli_args=cli_args)


def parse_nl_query(query: str) -> NLPlan:
    text = query.strip()
    if not text:
        raise ValueError("empty natural-language query")
    text_lower = text.lower()

    if _contains_any(text_lower, ("update", "升级", "更新", "拉取最新", "最新版本")):
        return _build_update_plan(text, text_lower)
    if _contains_any(text_lower, ("memory", "记忆", "复盘", "短期", "长期", "任务记录")):
        return _build_memory_plan(text, text, text_lower)
    if _contains_any(text_lower, ("skill", "技能")):
        return _build_skill_plan(text, text, text_lower)
    if _contains_any(text_lower, ("operator", "算子", "buffer", "缓冲", "单算法")):
        return _build_operator_plan(text, text, text_lower)
    return _build_run_plan(text, text, text_lower)
