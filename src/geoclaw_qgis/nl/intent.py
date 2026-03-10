from __future__ import annotations

from dataclasses import dataclass
import re

from geoclaw_qgis.profile import SessionProfile


BBOX_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)"
)
TOPN_RE = re.compile(r"(?:top\s*[-_ ]?n|前)\s*(\d{1,4})", re.IGNORECASE)
PATH_HINT_RE = re.compile(r"([~./\\A-Za-z0-9_\-]+/[A-Za-z0-9_\-./\\]+)")
CITY_EXPLICIT_RE = re.compile(r"(?:city|城市)\s*[:：]?\s*([A-Za-z\u4e00-\u9fff]{2,20})", re.IGNORECASE)
CITY_CN_RE = re.compile(r"(?:^|[^\u4e00-\u9fff])([\u4e00-\u9fff]{2,12}市)(?:[^\u4e00-\u9fff]|$)")
CITY_CN_REGION_RE = re.compile(r"(?:^|[^\u4e00-\u9fff])([\u4e00-\u9fff]{2,16}(?:市|州|县|区|旗|盟))(?:[^\u4e00-\u9fff]|$)")
CITY_CN_SIMPLE_RE = re.compile(r"([\u4e00-\u9fff]{2,12}市)")
CITY_CN_ACTION_RE = re.compile(
    r"(?:在|于|用|对|给|下载|基于|围绕)\s*([\u4e00-\u9fff]{2,16}(?:市|州|县|区|旗|盟)?)(?:的)?(?:数据|做|进行|开展|分析|选址|区位)"
)
CITY_EN_RE = re.compile(r"(?:\b(?:city|in|at)\b\s*[:：]?\s*)([A-Za-z][A-Za-z\-\s]{1,40})", re.IGNORECASE)
BACKTICK_RE = re.compile(r"`([^`]+)`")
LOCAL_CMD_INLINE_RE = re.compile(
    r"(?:执行(?:本地)?命令|运行(?:本地)?命令|run\s+local\s+cmd|run\s+command|shell)\s*[:：]?\s*(.+)$",
    re.IGNORECASE,
)
CHAT_KEYWORDS = (
    "你好",
    "您好",
    "hi",
    "hello",
    "hey",
    "谢谢",
    "thank",
    "闲聊",
    "聊天",
)
CHAT_REQUEST_HINTS = (
    "你是谁",
    "介绍你自己",
    "介绍一下你自己",
    "一句话介绍你自己",
    "陪我聊",
    "聊两句",
    "随便聊",
    "介绍下你自己",
    "who are you",
    "introduce yourself",
    "what can you do",
    "summarize what i asked",
    "summarize my previous",
)
SPATIAL_HINTS = (
    "run",
    "skill",
    "operator",
    "network",
    "reasoning",
    "bbox",
    "city",
    "城市",
    "区位",
    "选址",
    "地图",
    "出图",
    "轨迹",
    "od",
    "trackintel",
    "analysis",
    "spatial",
    "qgis",
    "分析",
    "下载",
    "商场",
    "地址",
    "报告",
    "建设",
)


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
    def _contains_term(haystack: str, needle: str) -> bool:
        token = needle.strip().lower()
        if not token:
            return False
        # CJK terms are matched by direct substring to avoid regex tokenization issues.
        if re.search(r"[\u4e00-\u9fff]", token):
            return token in haystack
        # For plain ASCII keywords, prefer token-aware matching to avoid false positives
        # like "od" in "introduce".
        if re.fullmatch(r"[a-z0-9]+", token):
            pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
            return re.search(pattern, haystack) is not None
        return token in haystack

    normalized = (text or "").lower()
    return any(_contains_term(normalized, t) for t in terms)


def _append_profile_reasons(reasons: list[str], session: SessionProfile | None) -> None:
    if session is None:
        return
    lang = session.user.preferred_language.strip()
    if lang:
        reasons.append(f"User preferred language={lang}.")
    if session.soul.execution_hierarchy:
        reasons.append(f"Execution hierarchy priority={session.soul.execution_hierarchy[0]}.")


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
    non_city_phrases = {
        "previous turn",
        "last turn",
        "one sentence",
        "this sentence",
        "that sentence",
        "my previous question",
        "your previous question",
    }
    non_city_tokens = {
        "previous",
        "last",
        "next",
        "one",
        "sentence",
        "turn",
        "question",
        "message",
        "summary",
        "summarize",
    }

    def _normalize_city_name(raw_city: str) -> str:
        city = raw_city.strip()
        city = re.sub(r"^(请你|请|帮我|帮忙)\s*", "", city)
        # Remove frequent leading function words in Chinese prompts.
        while len(city) > 2 and city[:1] in {"用", "在", "按", "对", "给"}:
            city = city[1:]
        city = city.strip(" ,，。.;；:：")
        city = city.rstrip("的")
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

    m2b = CITY_CN_SIMPLE_RE.search(text)
    if m2b:
        return _normalize_city_name(m2b.group(1))

    m3 = CITY_CN_REGION_RE.search(text)
    if m3:
        return _normalize_city_name(m3.group(1))

    m3b = CITY_CN_ACTION_RE.search(text)
    if m3b:
        city = _normalize_city_name(m3b.group(1))
        if city and city.endswith(("市", "州", "县", "区", "旗", "盟")):
            return city
        if city:
            return f"{city}市"

    m4 = CITY_EN_RE.search(text)
    if m4:
        city = _normalize_city_name(m4.group(1))
        if city:
            city_norm = re.sub(r"\s+", " ", city).strip()
            city_norm_lower = city_norm.lower()
            if city_norm_lower in non_city_phrases:
                return ""
            token_list = re.findall(r"[a-z]+", city_norm_lower)
            if token_list and any(tok in non_city_tokens for tok in token_list):
                return ""
            return city_norm
    return ""


def _detect_case(text: str, text_lower: str) -> str:
    if _contains_any(text, ("选址", "候选点", "site", "商场", "商业综合体", "mall")):
        return "site_selection"
    if _contains_any(text, ("区位", "location")):
        return "location_analysis"
    if _contains_any(text, ("综合", "advanced", "cluster", "聚类")):
        return "wuhan_advanced"
    if _contains_any(text_lower, ("native", "原生")):
        return "native_cases"
    if _contains_any(text, ("地图", "出图", "制图")):
        return "location_analysis"
    return "native_cases"


def _build_update_plan(query: str, text_lower: str, session: SessionProfile | None = None) -> NLPlan:
    reasons = ["Detected update-related keywords."]
    _append_profile_reasons(reasons, session)
    cli_args = ["update"]
    if _contains_any(text_lower, ("检查", "check", "是否有更新", "有没有更新", "只检查", "仅检查")):
        cli_args.append("--check-only")
        reasons.append("Using check-only mode.")
    return NLPlan(query=query, intent="update", confidence=0.97, reasons=reasons, cli_args=cli_args)


def _extract_local_command(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if raw.startswith("!"):
        return raw[1:].strip()
    if raw.lower().startswith("/tool "):
        return raw[6:].strip()

    match = BACKTICK_RE.search(raw)
    if match:
        return match.group(1).strip()

    inline = LOCAL_CMD_INLINE_RE.search(raw)
    if inline:
        return inline.group(1).strip().rstrip("。；;")
    return ""


def _build_local_tool_plan(query: str, text: str, session: SessionProfile | None = None) -> NLPlan:
    reasons = ["Detected local-tool execution request."]
    _append_profile_reasons(reasons, session)
    cmd = _extract_local_command(text)
    if not cmd:
        reasons.append("Command not parsed from NL text; fallback to chat.")
        return _build_chat_plan(query, text, session, extra_reasons=reasons)
    reasons.append(f"Parsed local command={cmd}.")
    return NLPlan(
        query=query,
        intent="local",
        confidence=0.91,
        reasons=reasons,
        cli_args=["local", "--cmd", cmd],
    )


def _build_chat_plan(
    query: str,
    text: str,
    session: SessionProfile | None = None,
    *,
    extra_reasons: list[str] | None = None,
) -> NLPlan:
    reasons = list(extra_reasons or [])
    reasons.append("Routed to chat mode.")
    _append_profile_reasons(reasons, session)
    return NLPlan(
        query=query,
        intent="chat",
        confidence=0.78,
        reasons=reasons,
        cli_args=["chat", "--message", text],
    )


def _is_conversational_chat_request(text: str, text_lower: str) -> bool:
    if _contains_any(text_lower, CHAT_REQUEST_HINTS):
        return True
    # Common "introduce yourself in one sentence" style requests.
    if _contains_any(text, ("介绍", "总结")) and _contains_any(text, ("你", "你自己")):
        return True
    return False


def _build_profile_plan(query: str, text: str, text_lower: str, session: SessionProfile | None = None) -> NLPlan:
    reasons = ["Detected profile-layer update keywords."]
    _append_profile_reasons(reasons, session)

    has_user = _contains_any(text_lower, ("user", "user.md", "用户", "画像", "偏好"))
    has_soul = _contains_any(text_lower, ("soul", "soul.md", "系统边界", "行为边界", "原则", "使命"))
    if has_user and has_soul:
        target = "both"
    elif has_soul:
        target = "soul"
    else:
        target = "user"

    cli_args = ["profile", "evolve", "--target", target, "--summary", query]
    if target in {"soul", "both"}:
        cli_args.append("--allow-soul")
        reasons.append("Target includes soul layer; enabled --allow-soul.")

    set_items: list[str] = []
    add_items: list[str] = []
    if target in {"user", "both"}:
        if _contains_any(text_lower, ("中文", "chinese")):
            set_items.append("preferred_language=Chinese")
        elif _contains_any(text_lower, ("英文", "english")):
            set_items.append("preferred_language=English")

        if _contains_any(text_lower, ("简洁", "concise")):
            set_items.append("preferred_tone=concise")
        elif _contains_any(text_lower, ("详细", "detailed")):
            set_items.append("preferred_tone=detailed")

        preferred_tools: list[str] = []
        if "ollama" in text_lower:
            preferred_tools.append("Ollama")
        if "openai" in text_lower:
            preferred_tools.append("OpenAI")
        if "qwen" in text_lower:
            preferred_tools.append("Qwen")
        if "gemini" in text_lower:
            preferred_tools.append("Gemini")
        if "qgis" in text_lower:
            preferred_tools.append("QGIS")
        if preferred_tools:
            add_items.append("preferred_tools=" + ",".join(dict.fromkeys(preferred_tools)))

    for item in set_items:
        cli_args.extend(["--set", item])
    for item in add_items:
        cli_args.extend(["--add", item])
    if set_items or add_items:
        reasons.append("Extracted profile preferences from NL text.")

    return NLPlan(query=query, intent="profile", confidence=0.9, reasons=reasons, cli_args=cli_args)


def _build_memory_plan(query: str, text: str, text_lower: str, session: SessionProfile | None = None) -> NLPlan:
    reasons = ["Detected memory-related keywords."]
    _append_profile_reasons(reasons, session)
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


def _build_skill_plan(query: str, text: str, text_lower: str, session: SessionProfile | None = None) -> NLPlan:
    reasons = ["Detected skill-related keywords."]
    _append_profile_reasons(reasons, session)
    if _contains_any(text_lower, ("list", "列表", "有哪些")):
        return NLPlan(
            query=query,
            intent="skill",
            confidence=0.93,
            reasons=reasons + ["Listing skills."],
            cli_args=["skill", "--", "--list"],
        )

    if _contains_any(text_lower, ("mall", "shopping", "商场", "商业综合体")):
        skill_id = "mall_site_selection_qgis"
        if _contains_any(text_lower, ("llm", "ai", "大模型")):
            skill_id = "mall_site_selection_llm"
        reasons.append(f"Resolved mall skill_id={skill_id}.")
        return NLPlan(
            query=query,
            intent="skill",
            confidence=0.95,
            reasons=reasons,
            cli_args=["skill", "--", "--skill", skill_id],
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


def _build_operator_plan(query: str, text: str, text_lower: str, session: SessionProfile | None = None) -> NLPlan:
    reasons = ["Detected operator/single-algorithm keywords."]
    _append_profile_reasons(reasons, session)
    distance = 800
    dist_m = re.search(r"(\d{2,6})\s*(?:m|米)", text_lower)
    if dist_m:
        distance = int(dist_m.group(1))
        reasons.append(f"Detected buffer distance={distance}.")

    output = "data/outputs/nl/operator_buffer.gpkg"
    in_path = "data/raw/input/hospitals.geojson"

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


def _build_network_plan(query: str, text: str, text_lower: str, session: SessionProfile | None = None) -> NLPlan:
    reasons = ["Detected complex-network/trackintel keywords."]
    _append_profile_reasons(reasons, session)
    pfs_path = "data/examples/trajectory/trackintel_demo_pfs.csv"
    out_dir = "data/outputs/network_trackintel_nl"
    paths = PATH_HINT_RE.findall(text)
    if len(paths) >= 1:
        pfs_path = paths[0]
        reasons.append(f"Detected pfs path={pfs_path}.")
    if len(paths) >= 2:
        out_dir = paths[1]
        reasons.append(f"Detected output dir={out_dir}.")
    cli_args = [
        "network",
        "--pfs-csv",
        pfs_path,
        "--out-dir",
        out_dir,
    ]
    if _contains_any(text_lower, ("dry-run", "dry run", "仅预览", "只预览")):
        cli_args.append("--dry-run")
        reasons.append("Enabled dry-run mode.")
    return NLPlan(query=query, intent="network", confidence=0.86, reasons=reasons, cli_args=cli_args)


def _build_run_plan(query: str, text: str, text_lower: str, session: SessionProfile | None = None) -> NLPlan:
    case = _detect_case(text, text_lower)
    cli_args = ["run", "--case", case]
    reasons = [f"Resolved case={case}."]
    _append_profile_reasons(reasons, session)

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
    elif session is not None and case in {"site_selection", "location_analysis", "native_cases"}:
        if _contains_any(" ".join(session.user.common_project_contexts).lower(), ("urban", "site", "location", "城市", "选址")):
            cli_args.extend(["--city", "武汉市"])
            reasons.append("No explicit source found; used profile default city=武汉市.")
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


def parse_nl_query(query: str, session: SessionProfile | None = None) -> NLPlan:
    text = query.strip()
    if not text:
        raise ValueError("empty natural-language query")
    text_lower = text.lower()

    if _contains_any(text_lower, ("执行命令", "运行命令", "local tool", "本地工具", "shell", "/tool ", "terminal")) or text.startswith("!"):
        return _build_local_tool_plan(text, text, session)
    if _contains_any(text_lower, ("profile", "user.md", "soul.md", "用户画像", "偏好", "系统边界", "行为边界")) and _contains_any(
        text_lower, ("更新", "修改", "同步", "写入", "evolve", "update", "adjust", "调整")
    ):
        return _build_profile_plan(text, text, text_lower, session)
    if _contains_any(text_lower, ("update", "updates", "升级", "更新", "拉取最新", "最新版本")):
        return _build_update_plan(text, text_lower, session)
    if _contains_any(text_lower, ("memory", "记忆", "复盘", "短期", "长期", "任务记录")):
        return _build_memory_plan(text, text, text_lower, session)
    if _is_conversational_chat_request(text, text_lower):
        return _build_chat_plan(text, text, session)
    if _contains_any(text_lower, ("skill", "技能")):
        return _build_skill_plan(text, text, text_lower, session)
    if _contains_any(text_lower, ("复杂网络", "network", "od", "trackintel", "流动网络")):
        return _build_network_plan(text, text, text_lower, session)
    if _contains_any(text_lower, ("operator", "算子", "buffer", "缓冲", "单算法")):
        return _build_operator_plan(text, text, text_lower, session)
    if _contains_any(text_lower, CHAT_KEYWORDS):
        return _build_chat_plan(text, text, session)
    if not _contains_any(text_lower, SPATIAL_HINTS):
        if not _detect_bbox(text) and not _detect_data_dir(text) and not _detect_city(text, text_lower):
            return _build_chat_plan(text, text, session)
    return _build_run_plan(text, text, text_lower, session)
