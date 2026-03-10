from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from geoclaw_qgis.ai import ExternalAIClient, ExternalAIConfig
from geoclaw_qgis.analysis import TrackintelIntegrationError, TrackintelNetworkService
from geoclaw_qgis.config import (
    bootstrap_runtime_env,
    detect_qgis_process,
    env_path,
    env_sh_path,
    geoclaw_home,
    parse_env_file,
    read_config,
    write_config,
    write_env,
    write_env_sh,
)
from geoclaw_qgis.identity import GEOCLAW_IDENTITY, is_identity_question
from geoclaw_qgis.memory import TaskMemoryStore
from geoclaw_qgis.nl import NLPlan, parse_nl_query
from geoclaw_qgis.profile import (
    SessionProfile,
    apply_dialogue_profile_update,
    ensure_profile_layers,
    load_session_profile,
)
from geoclaw_qgis.project_info import LAB_AFFILIATION, PROJECT_NAME, PROJECT_VERSION
from geoclaw_qgis.reasoning import run_spatial_reasoning
from geoclaw_qgis.reasoning.data_catalog_adapter import (
    dataset_spec_from_path,
    discover_datasets_from_dir,
    merge_dataset_specs,
)
from geoclaw_qgis.reasoning.input_adapter import build_reasoning_input_from_profile
from geoclaw_qgis.reasoning.report_generator import render_reasoning_report
from geoclaw_qgis.security import OutputSecurityError, fixed_output_root, validate_output_targets
from geoclaw_qgis.skills import (
    assess_skill_spec,
    load_openclaw_skill_spec,
    load_skill_spec_file,
    upsert_skill_registry,
)


DEFAULT_BBOX = "30.50,114.20,30.66,114.45"
DEFAULT_AI_PROVIDER = "openai"
DEFAULT_REGISTRY = "configs/skills_registry.json"
AI_PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5-mini",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus-latest",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-flash-latest",
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "llama3.1:8b",
    },
}
_SESSION_PROFILE: SessionProfile | None = None
_PATH_HINT_RE = re.compile(r"([~./A-Za-z0-9_\\-]+/[A-Za-z0-9_./\\-]+)")
_SRE_ALLOWED_ROOT_COMMANDS = {"run", "operator", "network", "skill", "memory", "update", "reasoning"}
_RUN_CASE_CHOICES = {"location_analysis", "site_selection", "native_cases", "wuhan_advanced"}
_SRE_SPATIAL_INTENTS = {"run", "operator", "network", "skill"}
_RUN_SOURCE_FLAGS = ("--data-dir", "--bbox", "--city")
_RUN_BOOL_FLAGS = ("--with-maps", "--no-maps", "--skip-download", "--force-download")
_RUN_VALUE_FLAGS = ("--top-n", "--timeout", "--tag", "--raw-dir", "--out-root")
_CHAT_EXIT_WORDS = {"exit", "quit", "q", "/exit", "/quit", "退出", "结束", "再见"}


def _has_flag_value(cmd: list[str], flag: str) -> bool:
    if flag not in cmd:
        return False
    idx = cmd.index(flag)
    return idx + 1 < len(cmd) and bool(str(cmd[idx + 1]).strip())


def _validate_sre_command_shape(cmd: list[str]) -> tuple[bool, str]:
    if not cmd:
        return False, "empty command"
    root = cmd[0]
    if root == "run":
        if not _has_flag_value(cmd, "--case"):
            return False, "run command missing --case"
        idx = cmd.index("--case")
        case = str(cmd[idx + 1]).strip()
        if case not in _RUN_CASE_CHOICES:
            return False, f"run command uses unsupported case={case}"
        return True, ""
    if root == "operator":
        if not _has_flag_value(cmd, "--algorithm"):
            return False, "operator command missing --algorithm"
        return True, ""
    if root == "network":
        if not _has_flag_value(cmd, "--pfs-csv"):
            return False, "network command missing --pfs-csv"
        return True, ""
    if root == "skill":
        if "--skill" in cmd and _has_flag_value(cmd, "--skill"):
            return True, ""
        if "--list" in cmd:
            return True, ""
        return False, "skill command missing --skill/--list"
    return True, ""


def _is_sre_route_compatible(*, base_intent: str, new_root: str) -> bool:
    intent = str(base_intent or "").strip().lower()
    root = str(new_root or "").strip().lower()
    if not intent:
        return True
    if intent == "run":
        return root in {"run", "skill"}
    if intent == "operator":
        return root in {"operator", "skill"}
    if intent == "network":
        return root in {"network", "skill"}
    if intent == "skill":
        return root == "skill"
    return False


def _set_reasoner_env_overrides(*, mode: str = "", retries: int | None = None, strict_external: bool = False) -> None:
    mode_clean = str(mode or "").strip().lower()
    if mode_clean in {"auto", "deterministic", "external"}:
        os.environ["GEOCLAW_SRE_REASONER_MODE"] = mode_clean
    if retries is not None and int(retries) > 0:
        os.environ["GEOCLAW_SRE_LLM_MAX_RETRIES"] = str(int(retries))
    if bool(strict_external):
        os.environ["GEOCLAW_SRE_STRICT_EXTERNAL"] = "1"


def ask_value(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else default


def _mask_api_key(value: str, *, head: int = 4, tail: int = 4) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= head + tail:
        return text[:1] + "*" * max(0, len(text) - 2) + text[-1:] if len(text) > 2 else "*" * len(text)
    return f"{text[:head]}***{text[-tail:]}"


def ask_api_key(prompt: str, existing_key: str = "") -> str:
    masked = _mask_api_key(existing_key)
    suffix = f" [当前: {masked}, 回车保持]" if masked else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else str(existing_key or "").strip()


def cmd_onboard(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    existing = read_config()

    defaults = existing.get("defaults") if isinstance(existing.get("defaults"), dict) else {}
    runtime = existing.get("runtime") if isinstance(existing.get("runtime"), dict) else {}

    ai_provider = str(args.ai_provider or defaults.get("ai_provider", DEFAULT_AI_PROVIDER)).strip().lower()
    if ai_provider not in AI_PROVIDER_PRESETS:
        raise ValueError(f"unsupported --ai-provider: {ai_provider}. choices={sorted(AI_PROVIDER_PRESETS.keys())}")

    provider_defaults = AI_PROVIDER_PRESETS[ai_provider]
    previous_provider = str(defaults.get("ai_provider", DEFAULT_AI_PROVIDER)).strip().lower() or DEFAULT_AI_PROVIDER
    api_base_url = args.ai_base_url or str(defaults.get("ai_base_url", "")).strip()
    ai_model = args.ai_model or str(defaults.get("ai_model", "")).strip()
    if not api_base_url or (not args.ai_base_url and ai_provider != previous_provider):
        api_base_url = provider_defaults["base_url"]
    if not ai_model or (not args.ai_model and ai_provider != previous_provider):
        ai_model = provider_defaults["model"]
    if args.ai_provider and not args.ai_base_url:
        api_base_url = provider_defaults["base_url"]
    if args.ai_provider and not args.ai_model:
        ai_model = provider_defaults["model"]
    default_bbox = args.default_bbox or defaults.get("bbox", DEFAULT_BBOX)
    registry_path = args.registry or defaults.get("registry", DEFAULT_REGISTRY)
    workspace = args.workspace or defaults.get("workspace", str(Path.cwd().resolve()))

    detected_qgis = ""
    try:
        detected_qgis = detect_qgis_process(args.qgis_process or runtime.get("qgis_process", ""))
    except FileNotFoundError:
        detected_qgis = ""

    existing_key = (
        os.environ.get("GEOCLAW_AI_API_KEY", "").strip()
        or os.environ.get("GEOCLAW_OPENAI_API_KEY", "").strip()
        or os.environ.get("GEOCLAW_QWEN_API_KEY", "").strip()
        or os.environ.get("GEOCLAW_GEMINI_API_KEY", "").strip()
        or os.environ.get("GEOCLAW_OLLAMA_API_KEY", "").strip()
    )

    if not args.non_interactive:
        print(f"GeoClaw-OpenAI home: {geoclaw_home()}")
        ai_provider = ask_value("AI Provider (openai/qwen/gemini/ollama)", ai_provider).strip().lower() or ai_provider
        if ai_provider not in AI_PROVIDER_PRESETS:
            raise ValueError(f"unsupported AI provider: {ai_provider}")
        provider_defaults = AI_PROVIDER_PRESETS[ai_provider]
        if not args.ai_base_url and api_base_url == defaults.get("ai_base_url", ""):
            api_base_url = provider_defaults["base_url"]
        if not args.ai_model and ai_model == defaults.get("ai_model", ""):
            ai_model = provider_defaults["model"]
        api_base_url = ask_value("AI Base URL", api_base_url)
        ai_model = ask_value("AI Model", ai_model)
        default_bbox = ask_value("Default BBOX (south,west,north,east)", default_bbox)
        registry_path = ask_value("Skill registry path", registry_path)
        workspace = ask_value("Default workspace path", workspace)

        qgis_prompt_default = detected_qgis or args.qgis_process or ""
        qgis_input = ask_value("qgis_process path", qgis_prompt_default)
        if qgis_input:
            try:
                detected_qgis = detect_qgis_process(qgis_input)
            except FileNotFoundError:
                print("[WARN] qgis_process 路径无效，将仅写入原值")
                detected_qgis = qgis_input

        api_key = args.api_key or ask_api_key(f"{ai_provider.upper()} API Key", existing_key=existing_key)
    else:
        api_key = args.api_key or existing_key
        if not detected_qgis:
            detected_qgis = args.qgis_process or runtime.get("qgis_process", "")

    if ai_provider == "ollama" and not api_key:
        api_key = "ollama-local"
    if not api_key:
        raise ValueError("AI API key is required. Use --api-key or run interactive onboard.")

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        "version": PROJECT_VERSION,
        "updated_at": now,
        "defaults": {
            "ai_provider": ai_provider,
            "ai_base_url": api_base_url,
            "ai_model": ai_model,
            "bbox": default_bbox,
            "registry": registry_path,
            "workspace": workspace,
        },
        "runtime": {
            "qgis_process": detected_qgis,
        },
    }
    if "created_at" in existing:
        payload["created_at"] = existing["created_at"]
    else:
        payload["created_at"] = now

    env_values = {
        "GEOCLAW_AI_PROVIDER": ai_provider,
        "GEOCLAW_AI_BASE_URL": api_base_url,
        "GEOCLAW_AI_API_KEY": api_key,
        "GEOCLAW_AI_MODEL": ai_model,
        "GEOCLAW_OPENAI_BASE_URL": api_base_url,
        "GEOCLAW_OPENAI_API_KEY": api_key,
        "GEOCLAW_OPENAI_MODEL": ai_model,
        "GEOCLAW_OPENAI_DEFAULT_BBOX": default_bbox,
        "GEOCLAW_OPENAI_SKILL_REGISTRY": registry_path,
        "GEOCLAW_OPENAI_WORKSPACE": workspace,
    }
    if ai_provider == "qwen":
        env_values["GEOCLAW_QWEN_BASE_URL"] = api_base_url
        env_values["GEOCLAW_QWEN_API_KEY"] = api_key
        env_values["GEOCLAW_QWEN_MODEL"] = ai_model
    if ai_provider == "gemini":
        env_values["GEOCLAW_GEMINI_BASE_URL"] = api_base_url
        env_values["GEOCLAW_GEMINI_API_KEY"] = api_key
        env_values["GEOCLAW_GEMINI_MODEL"] = ai_model
    if ai_provider == "ollama":
        env_values["GEOCLAW_OLLAMA_BASE_URL"] = api_base_url
        env_values["GEOCLAW_OLLAMA_MODEL"] = ai_model
        if api_key:
            env_values["GEOCLAW_OLLAMA_API_KEY"] = api_key
    if detected_qgis:
        env_values["GEOCLAW_OPENAI_QGIS_PROCESS"] = detected_qgis

    config_file = write_config(payload)
    env_file = write_env(env_values)
    env_sh = write_env_sh(env_values)
    profile_paths = ensure_profile_layers(Path(workspace).expanduser().resolve())

    print(json.dumps({
        "config": str(config_file),
        "env": str(env_file),
        "env_sh": str(env_sh),
        "qgis_process": detected_qgis,
        "registry": registry_path,
        "profile_layers": {
            "home_soul": profile_paths["home_soul"],
            "home_user": profile_paths["home_user"],
        },
    }, ensure_ascii=False, indent=2))

    print("\nNext:")
    print(f"1) source {env_sh_path()}")
    print("2) geoclaw-openai config show")
    print("3) geoclaw-openai skill -- --list")
    return 0


def cmd_config_show(_args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    cfg = read_config()
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    existing = read_config()
    defaults = existing.get("defaults") if isinstance(existing.get("defaults"), dict) else {}
    runtime = existing.get("runtime") if isinstance(existing.get("runtime"), dict) else {}

    current_provider = str(defaults.get("ai_provider", DEFAULT_AI_PROVIDER)).strip().lower() or DEFAULT_AI_PROVIDER
    ai_provider = str(args.ai_provider or current_provider).strip().lower()
    if ai_provider not in AI_PROVIDER_PRESETS:
        raise ValueError(f"unsupported --ai-provider: {ai_provider}. choices={sorted(AI_PROVIDER_PRESETS.keys())}")
    provider_changed = bool(args.ai_provider) and ai_provider != current_provider
    preset = AI_PROVIDER_PRESETS[ai_provider]

    ai_base_url = str(args.ai_base_url or "").strip()
    if not ai_base_url:
        if provider_changed:
            ai_base_url = preset["base_url"]
        else:
            ai_base_url = str(defaults.get("ai_base_url", "")).strip() or preset["base_url"]

    ai_model = str(args.ai_model or "").strip()
    if not ai_model:
        if provider_changed:
            ai_model = preset["model"]
        else:
            ai_model = str(defaults.get("ai_model", "")).strip() or preset["model"]

    default_bbox = str(args.default_bbox or defaults.get("bbox", DEFAULT_BBOX)).strip() or DEFAULT_BBOX
    registry_path = str(args.registry or defaults.get("registry", DEFAULT_REGISTRY)).strip() or DEFAULT_REGISTRY
    workspace = str(args.workspace or defaults.get("workspace", str(Path.cwd().resolve()))).strip()

    qgis_process = str(args.qgis_process or runtime.get("qgis_process", "")).strip()
    if qgis_process:
        try:
            qgis_process = detect_qgis_process(qgis_process)
        except FileNotFoundError:
            pass

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        "version": PROJECT_VERSION,
        "updated_at": now,
        "defaults": {
            "ai_provider": ai_provider,
            "ai_base_url": ai_base_url,
            "ai_model": ai_model,
            "bbox": default_bbox,
            "registry": registry_path,
            "workspace": workspace,
        },
        "runtime": {
            "qgis_process": qgis_process,
        },
        "created_at": existing.get("created_at", now),
    }

    env_values = parse_env_file(env_path())
    existing_api_key = (
        env_values.get("GEOCLAW_AI_API_KEY", "").strip()
        or env_values.get("GEOCLAW_OPENAI_API_KEY", "").strip()
        or env_values.get("GEOCLAW_QWEN_API_KEY", "").strip()
        or env_values.get("GEOCLAW_GEMINI_API_KEY", "").strip()
        or env_values.get("GEOCLAW_OLLAMA_API_KEY", "").strip()
    )
    api_key = str(args.api_key or existing_api_key).strip()
    if ai_provider == "ollama" and not api_key:
        api_key = "ollama-local"

    env_values.update(
        {
            "GEOCLAW_AI_PROVIDER": ai_provider,
            "GEOCLAW_AI_BASE_URL": ai_base_url,
            "GEOCLAW_AI_MODEL": ai_model,
            "GEOCLAW_OPENAI_BASE_URL": ai_base_url,
            "GEOCLAW_OPENAI_MODEL": ai_model,
            "GEOCLAW_OPENAI_DEFAULT_BBOX": default_bbox,
            "GEOCLAW_OPENAI_SKILL_REGISTRY": registry_path,
            "GEOCLAW_OPENAI_WORKSPACE": workspace,
        }
    )
    if api_key:
        env_values["GEOCLAW_AI_API_KEY"] = api_key
        env_values["GEOCLAW_OPENAI_API_KEY"] = api_key
    if qgis_process:
        env_values["GEOCLAW_OPENAI_QGIS_PROCESS"] = qgis_process

    if ai_provider == "qwen":
        env_values["GEOCLAW_QWEN_BASE_URL"] = ai_base_url
        env_values["GEOCLAW_QWEN_MODEL"] = ai_model
        if api_key:
            env_values["GEOCLAW_QWEN_API_KEY"] = api_key
    if ai_provider == "gemini":
        env_values["GEOCLAW_GEMINI_BASE_URL"] = ai_base_url
        env_values["GEOCLAW_GEMINI_MODEL"] = ai_model
        if api_key:
            env_values["GEOCLAW_GEMINI_API_KEY"] = api_key
    if ai_provider == "ollama":
        env_values["GEOCLAW_OLLAMA_BASE_URL"] = ai_base_url
        env_values["GEOCLAW_OLLAMA_MODEL"] = ai_model
        if api_key:
            env_values["GEOCLAW_OLLAMA_API_KEY"] = api_key

    config_file = write_config(payload)
    env_file = write_env(env_values)
    env_sh = write_env_sh(env_values)
    print(
        json.dumps(
            {
                "config": str(config_file),
                "env": str(env_file),
                "env_sh": str(env_sh),
                "ai_provider": ai_provider,
                "ai_model": ai_model,
                "ai_base_url": ai_base_url,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_env(_args: argparse.Namespace) -> int:
    path = env_sh_path()
    if not path.exists():
        print(f"env script not found: {path}")
        return 1
    print(f"source {path}")
    return 0


def get_session_profile(*, force_reload: bool = False) -> SessionProfile:
    global _SESSION_PROFILE
    if _SESSION_PROFILE is None or force_reload:
        _SESSION_PROFILE = load_session_profile(resolve_workspace_root(), force_reload=force_reload)
    return _SESSION_PROFILE


def cmd_profile_init(_args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    payload = ensure_profile_layers(resolve_workspace_root())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_profile_show(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    session = get_session_profile(force_reload=bool(args.reload))
    print(json.dumps(session.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _parse_set_pairs(values: list[str]) -> dict[str, str]:
    payload: dict[str, str] = {}
    for raw in values:
        item = str(raw or "").strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"invalid --set item: {item}. expected KEY=VALUE")
        key, value = item.split("=", 1)
        k = key.strip().lower()
        v = value.strip()
        if not k:
            raise ValueError(f"invalid --set item: {item}. empty key")
        if not v:
            raise ValueError(f"invalid --set item: {item}. empty value")
        payload[k] = v
    return payload


def _parse_add_pairs(values: list[str]) -> dict[str, list[str]]:
    payload: dict[str, list[str]] = {}
    for raw in values:
        item = str(raw or "").strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"invalid --add item: {item}. expected KEY=VALUE1,VALUE2")
        key, value = item.split("=", 1)
        k = key.strip().lower()
        if not k:
            raise ValueError(f"invalid --add item: {item}. empty key")
        text = value.strip()
        if not text:
            raise ValueError(f"invalid --add item: {item}. empty value")
        if ";" in text:
            items = [x.strip() for x in text.split(";")]
        elif "|" in text:
            items = [x.strip() for x in text.split("|")]
        else:
            items = [x.strip() for x in text.split(",")]
        clean = [x for x in items if x]
        if not clean:
            raise ValueError(f"invalid --add item: {item}. empty parsed values")
        payload[k] = clean
    return payload


def cmd_profile_evolve(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    set_values = _parse_set_pairs(list(args.set_items or []))
    add_values = _parse_add_pairs(list(args.add_items or []))
    summary = str(args.summary or "").strip()

    target = str(args.target or "user").strip().lower()
    targets = ["user", "soul"] if target == "both" else [target]
    if "soul" in targets and not bool(args.allow_soul):
        raise ValueError(
            "Updating soul.md from dialogue requires --allow-soul. "
            "Safety/execution boundary keys remain locked regardless."
        )

    results: list[dict[str, object]] = []
    for current in targets:
        results.append(
            apply_dialogue_profile_update(
                target=current,
                summary=summary,
                set_values=set_values,
                add_values=add_values,
                workspace_root=resolve_workspace_root(),
                dry_run=bool(args.dry_run),
            )
        )

    profile_payload: dict[str, object] = {}
    if not bool(args.dry_run):
        profile_payload = get_session_profile(force_reload=True).to_dict()

    print(
        json.dumps(
            {
                "target": target,
                "dry_run": bool(args.dry_run),
                "updates": results,
                "profile": profile_payload,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _chat_suggestions(message: str, session: SessionProfile) -> list[str]:
    text = str(message or "").strip().lower()
    lang = session.user.preferred_language.strip().lower()
    english = "english" in lang and "chinese" not in lang
    if english:
        suggestions = [
            "For spatial analysis, you can ask: `Top 5 mall locations in <your city>`.",
            "To preview executable command, run: `geoclaw-openai nl \"your request\"`.",
            "To execute directly, add: `--execute`.",
        ]
    else:
        suggestions = [
            "如果是空间分析任务，可直接说：`武汉最适合建商场的前5个地点`。",
            "如需查看可执行命令，先用：`geoclaw-openai nl \"你的问题\"`（预览模式）。",
            "如需直接运行，请加：`--execute`。",
        ]
    if any(k in text for k in ("报错", "error", "失败", "无法", "can't", "cannot")):
        if english:
            suggestions.insert(0, "Please share the exact error, command, and input path; I will provide a step-by-step fix.")
        else:
            suggestions.insert(0, "先提供报错原文、输入数据路径、你执行的完整命令，我会给出逐步修复方案。")
    if any(k in text for k in ("命令", "shell", "tool", "工具")):
        if english:
            suggestions.append("To run a local command: `geoclaw-openai local --cmd \"<your command>\"`.")
        else:
            suggestions.append("如需调用本地命令：`geoclaw-openai local --cmd \"<your command>\"`。")
    return suggestions


def _contains_any(text_lower: str, keywords: tuple[str, ...]) -> bool:
    return any(k in text_lower for k in keywords)


def _fallback_chitchat_reply_zh(text: str, *, memory_hint: str = "") -> str:
    tl = text.lower()

    if _contains_any(tl, ("高质量对话",)):
        return "高质量对话=目标清晰、信息真实、下一步可执行。"
    if _contains_any(tl, ("沟通", "交流")) and _contains_any(tl, ("三个", "3")) and _contains_any(tl, ("技巧",)):
        return "三个技巧：1) 先说结论；2) 再给依据；3) 最后明确下一步和截止时间。"
    if _contains_any(tl, ("平衡效率和耐心", "效率和耐心")):
        return "先用一句话确认需求，再给最多3步建议；每步都留1个确认点，既快又不冒进。"
    if _contains_any(tl, ("状态一般", "没状态", "有点累")) and _contains_any(tl, ("推进", "前进", "一点点")):
        return "先做15分钟最小任务：写目标一句话、列3个子任务、完成第1个子任务的第一步。"
    if _contains_any(tl, ("焦虑",)) and _contains_any(tl, ("拆小", "拆分")):
        return "把任务拆成三层：今天必须完成1件、可选完成2件、以后再做其余；先做“必须完成”的第一步。"
    if _contains_any(tl, ("明确目标",)) and _contains_any(tl, ("问题", "提问")):
        return "你最希望今天结束前“可见”的成果是什么（文档、图、表、还是一个可运行命令）？"
    if _contains_any(tl, ("追问", "更具体的问题")):
        return "如果只能选一个动作现在就做，它是什么，完成它需要的最小输入是什么？"
    if _contains_any(tl, ("清单模板", "checklist")):
        return "极简清单：1) 目标一句话；2) 三个子任务；3) 先做哪一个；4) 完成标准；5) 截止时间。"
    if _contains_any(tl, ("安抚",)) and _contains_any(tl, ("示例", "回复")):
        return "我知道你现在有压力，我们先只做一件最小可完成的事：把目标写成一句话，我陪你一步步推进。"
    if _contains_any(tl, ("纠结细节", "拉回主线", "主线")):
        return "先回到主问题：这件事的成功标准是什么？不影响标准的细节先标记到“后处理”清单。"
    if _contains_any(tl, ("聊天风格", "总结一下")):
        return "目前风格偏务实和结构化：你给场景，我给可执行步骤；优先明确目标，再收敛到下一步。"
    if _contains_any(tl, ("晚间回顾", "复盘")) and _contains_any(tl, ("提问框架", "框架")):
        return "晚间回顾框架：今天做成了什么？卡在哪里？明天第一步做什么？"
    if _contains_any(tl, ("三问", "简化")):
        return "三问版：1) 今天最关键成果？2) 最大阻碍？3) 明天第一步？"
    if _contains_any(tl, ("更有温度", "语气自然", "像同事")):
        return "可以，我会保持直给建议，同时用更自然的表达，不堆术语，也不空话。"
    if _contains_any(tl, ("沟通句式", "句式")):
        return "实用句式：先说结论“我建议先做A”，再说原因“因为B”，最后说动作“现在我先完成C”。"
    if _contains_any(tl, ("很累",)) and _contains_any(tl, ("一句话回应", "一句话")):
        return "你先休息5分钟，我们只推进一个最小步骤，做完就算今天有进展。"
    if _contains_any(tl, ("鼓励", "务实")):
        return "你不需要一次做完全部，只要把下一步做实，项目就已经在前进。"
    if _contains_any(tl, ("收尾", "两句话")):
        return "今天你已经把方向和节奏理清了，这很关键。明天从最小可执行步骤开始，我继续协助你推进。"

    base = "我理解你的问题。先给你一个可执行建议：明确目标一句话，然后立刻做第一步。"
    if memory_hint:
        base += f" 最近复盘提醒：{memory_hint}"
    return base


def _fallback_chitchat_reply_en(text: str, *, memory_hint: str = "") -> str:
    tl = text.lower()
    if _contains_any(tl, ("high-quality conversation", "good conversation")):
        return "A high-quality conversation is clear on goals, honest on constraints, and ends with an executable next step."
    if _contains_any(tl, ("three", "3")) and _contains_any(tl, ("communication", "tips")):
        return "Three tips: lead with conclusion, add evidence, and finish with one concrete next action plus deadline."
    if _contains_any(tl, ("checklist", "template")):
        return "Mini checklist: goal in one line, 3 subtasks, first action now, done criteria, deadline."
    if _contains_any(tl, ("wrap up", "two sentences", "closing")):
        return "You clarified direction and priorities today. Start tomorrow with the smallest executable action and keep momentum."
    if _contains_any(tl, ("encourage", "practical")):
        return "You do not need to finish everything at once; one solid next step is real progress."

    base = "I understand your question. Practical next step: write your goal in one sentence, then execute the first small action now."
    if memory_hint:
        base += f" Recent review reminder: {memory_hint}"
    return base


def _fallback_chat_reply(
    message: str,
    session: SessionProfile,
    *,
    memory_context: dict[str, object] | None = None,
) -> str:
    text = str(message or "").strip()
    lang = session.user.preferred_language.strip().lower()
    tone = session.user.preferred_tone.strip().lower()
    mission = session.soul.mission.strip()
    english = "english" in lang and "chinese" not in lang
    detailed = "detailed" in tone or "详细" in tone or "step-by-step" in tone
    memory_hint = ""
    if isinstance(memory_context, dict):
        summaries = [str(x).strip() for x in (memory_context.get("recent_long_summaries") or []) if str(x).strip()]
        if summaries:
            memory_hint = _clip_prompt_text(summaries[0], max_chars=120)
    if not text:
        if english:
            return "Tell me your goal and I can help plan an executable GeoClaw workflow."
        return "请告诉我你的目标，我可以协助你规划 GeoClaw 工作流。"
    if is_identity_question(text):
        if english:
            return GEOCLAW_IDENTITY.answer_en()
        return GEOCLAW_IDENTITY.answer_zh()
    if any(k in text.lower() for k in ("报错", "error", "失败", "无法", "can't", "cannot")):
        if english:
            return (
                f"Mission: {mission or 'Reliable geospatial analysis'}. "
                "I cannot resolve all context yet. Share the stack trace, input path, and command; "
                "I will provide actionable debug steps."
            )
        return (
            f"系统使命：{mission or '可靠、可复现的地理分析'}。"
            "我暂时无法直接定位全部上下文。请提供报错堆栈、输入路径和执行命令，我会给你可执行的修复步骤。"
        )
    if any(k in text for k in ("你好", "您好")):
        if english:
            return "Hello. I can chat and also convert your request into executable GeoClaw commands."
        return "你好，我可以闲聊，也可以帮你把需求转成可执行的 GeoClaw 命令。"
    if english:
        return _fallback_chitchat_reply_en(text, memory_hint=memory_hint)
    return _fallback_chitchat_reply_zh(text, memory_hint=memory_hint)


def _utc_iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _chat_sessions_dir() -> Path:
    path = geoclaw_home() / "chat" / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_chat_session_id(raw: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(raw or "").strip())
    text = text.strip("._-")
    return text


def _new_chat_session_id() -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"chat_{stamp}_{uuid.uuid4().hex[:6]}"


def _chat_session_path(session_id: str) -> Path:
    return _chat_sessions_dir() / f"{session_id}.json"


def _load_chat_session(session_id: str) -> tuple[dict[str, object], Path]:
    sid = _normalize_chat_session_id(session_id)
    if not sid:
        raise ValueError("invalid chat session_id")
    path = _chat_session_path(sid)
    now = _utc_iso_now()
    if not path.exists():
        payload: dict[str, object] = {
            "session_id": sid,
            "created_at": now,
            "updated_at": now,
            "turns": [],
        }
        return payload, path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    turns = payload.get("turns")
    if not isinstance(turns, list):
        turns = []
    payload["session_id"] = str(payload.get("session_id", sid) or sid)
    payload["created_at"] = str(payload.get("created_at", now) or now)
    payload["updated_at"] = str(payload.get("updated_at", now) or now)
    payload["turns"] = [x for x in turns if isinstance(x, dict)]
    return payload, path


def _save_chat_session(payload: dict[str, object], path: Path) -> None:
    data = dict(payload)
    data["updated_at"] = _utc_iso_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _chat_history_text(
    turns: list[dict[str, object]],
    *,
    max_turns: int = 8,
    max_chars: int = 6000,
) -> str:
    tail = list(turns)[-max(1, int(max_turns)) :]
    lines: list[str] = []
    for item in tail:
        user_text = str(item.get("user", "")).strip()
        assistant_text = str(item.get("assistant", "")).strip()
        if user_text:
            lines.append(f"User: {user_text}")
        if assistant_text:
            lines.append(f"Assistant: {assistant_text}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[-max_chars:]
    return text


def _append_chat_turn(
    payload: dict[str, object],
    *,
    message: str,
    chat: dict[str, object],
) -> dict[str, object]:
    turns_raw = payload.get("turns")
    turns: list[dict[str, object]]
    if isinstance(turns_raw, list):
        turns = [x for x in turns_raw if isinstance(x, dict)]
    else:
        turns = []
    turns.append(
        {
            "ts": _utc_iso_now(),
            "user": str(message or "").strip(),
            "assistant": str(chat.get("reply", "")).strip(),
            "mode": str(chat.get("mode", "")).strip(),
        }
    )
    payload["turns"] = turns
    payload["updated_at"] = _utc_iso_now()
    return payload


def _safe_chat_memory_session_id(raw: str) -> str:
    sid = _normalize_chat_session_id(raw)
    return sid or "adhoc"


def _clip_prompt_text(text: str, *, max_chars: int = 220) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max(1, max_chars - 3)] + "..."


def _profile_context_block(session: SessionProfile) -> str:
    tools = ", ".join(session.user.preferred_tools[:5]) if session.user.preferred_tools else ""
    outputs = ", ".join(session.user.output_preferences[:5]) if session.user.output_preferences else ""
    constraints = "; ".join(session.user.long_term_constraints[:3]) if session.user.long_term_constraints else ""
    mission = _clip_prompt_text(session.soul.mission, max_chars=180)
    standards = "; ".join(session.soul.output_quality_standards[:3]) if session.soul.output_quality_standards else ""
    lines = [
        f"User role: {session.user.role}",
        f"Preferred language: {session.user.preferred_language}",
        f"Preferred tone: {session.user.preferred_tone}",
    ]
    if tools:
        lines.append(f"Preferred tools: {tools}")
    if outputs:
        lines.append(f"Output preferences: {outputs}")
    if constraints:
        lines.append(f"Long-term constraints: {constraints}")
    if mission:
        lines.append(f"Soul mission: {mission}")
    if standards:
        lines.append(f"Output quality standards: {standards}")
    return "\n".join(lines)


def _memory_hit_line(hit: dict[str, Any]) -> str:
    source = str(hit.get("source", "")).strip() or "memory"
    score = hit.get("score")
    payload = hit.get("payload")
    data = payload if isinstance(payload, dict) else {}
    task_id = str(data.get("task_id", "")).strip()
    command = str(data.get("command", "")).strip()
    status = str(data.get("status", "")).strip()
    summary = str(data.get("summary", "")).strip()
    review = data.get("review")
    if not summary and isinstance(review, dict):
        summary = str(review.get("summary", "")).strip()
    text = f"[{source}] task={task_id} command={command} status={status}"
    if summary:
        text += f" summary={_clip_prompt_text(summary, max_chars=160)}"
    if isinstance(score, (float, int)):
        text += f" score={round(float(score), 3)}"
    return text


def _collect_chat_memory_context(
    *,
    message: str,
    session: SessionProfile,
    session_id: str,
) -> dict[str, object]:
    try:
        store = TaskMemoryStore(session_profile=session)
        top_k_raw = str(os.environ.get("GEOCLAW_CHAT_MEMORY_TOP_K", "3")).strip() or "3"
        min_score_raw = str(os.environ.get("GEOCLAW_CHAT_MEMORY_MIN_SCORE", "0.12")).strip() or "0.12"
        long_limit_raw = str(os.environ.get("GEOCLAW_CHAT_LONG_LIMIT", "3")).strip() or "3"
        top_k = max(1, int(top_k_raw))
        min_score = max(0.0, float(min_score_raw))
        long_limit = max(1, int(long_limit_raw))

        hits_raw = store.search_memory(query=message, scope="all", top_k=max(8, top_k * 3), min_score=min_score)
        hits: list[dict[str, object]] = []
        for hit in hits_raw:
            payload = hit.get("payload")
            if not isinstance(payload, dict):
                continue
            command = str(payload.get("command", "")).strip().lower()
            extra = payload.get("extra")
            memory_kind = str((extra or {}).get("memory_kind", "")).strip().lower() if isinstance(extra, dict) else ""
            if command in {"memory", "nl"}:
                continue
            if command == "chat" and memory_kind != "chat_daily":
                continue
            hits.append(hit)
            if len(hits) >= top_k:
                break
        daily = store.get_chat_daily_digest(session_id=_safe_chat_memory_session_id(session_id))
        recent_long = store.list_long(limit=long_limit)
        long_summaries: list[str] = []
        for row in recent_long[:long_limit]:
            command = str(row.get("command", "")).strip().lower()
            if command in {"chat", "memory", "nl", "profile"}:
                continue
            summary = str(row.get("summary", "")).strip()
            if summary:
                long_summaries.append(_clip_prompt_text(summary, max_chars=180))
        return {
            "daily_digest": daily,
            "relevant_hits": hits,
            "recent_long_summaries": long_summaries,
        }
    except Exception as exc:
        return {"warning": f"memory context unavailable: {exc}"}


def _chat_memory_context_block(memory_context: dict[str, object]) -> str:
    lines: list[str] = []
    daily = memory_context.get("daily_digest")
    if isinstance(daily, dict) and daily:
        turn_count = int(daily.get("turn_count", 0) or 0)
        intents = [str(x) for x in (daily.get("intents") or []) if str(x).strip()]
        modes = [str(x) for x in (daily.get("modes") or []) if str(x).strip()]
        last_turn_at = str(daily.get("last_turn_at", "")).strip()
        lines.append(
            f"Daily dialogue digest: turns={turn_count}, intents={','.join(intents[:6])}, modes={','.join(modes[:6])}, last_turn_at={last_turn_at}"
        )
        recent_turns = [x for x in (daily.get("recent_turns") or []) if isinstance(x, dict)]
        for item in recent_turns[-2:]:
            user_text = _clip_prompt_text(str(item.get("user", "")), max_chars=80)
            if user_text:
                lines.append(f"Recent user topic: {user_text}")

    summaries = [str(x).strip() for x in (memory_context.get("recent_long_summaries") or []) if str(x).strip()]
    if summaries:
        lines.append("Recent reviewed memories:")
        for item in summaries[:3]:
            lines.append(f"- {item}")

    hits = [x for x in (memory_context.get("relevant_hits") or []) if isinstance(x, dict)]
    if hits:
        lines.append("Relevant memory retrieval:")
        for hit in hits[:4]:
            lines.append(f"- {_memory_hit_line(hit)}")
    warning = str(memory_context.get("warning", "")).strip()
    if warning:
        lines.append(f"Memory warning: {warning}")
    return "\n".join(lines)


def _record_chat_turn_memory(
    *,
    session: SessionProfile,
    session_id: str,
    message: str,
    chat_payload: dict[str, object],
    intent: str,
) -> dict[str, object]:
    try:
        store = TaskMemoryStore(session_profile=session)
        row = store.record_chat_turn(
            session_id=_safe_chat_memory_session_id(session_id),
            user_message=message,
            assistant_reply=str(chat_payload.get("reply", "")),
            intent=intent,
            mode=str(chat_payload.get("mode", "")),
            event_time=_utc_iso_now(),
            cwd=str(Path.cwd().resolve()),
        )
        digest = row.get("chat_digest")
        turn_count = int(digest.get("turn_count", 0)) if isinstance(digest, dict) else 0
        return {
            "task_id": str(row.get("task_id", "")),
            "turn_count": turn_count,
            "session_id": _safe_chat_memory_session_id(session_id),
            "date": str((row.get("extra") or {}).get("date", "")),
        }
    except Exception as exc:
        return {"warning": str(exc)}


def _parse_profile_evolve_cli_args(cli_args: list[str]) -> dict[str, object]:
    args = [str(x).strip() for x in cli_args if str(x).strip()]
    if len(args) < 2 or args[0] != "profile" or args[1] != "evolve":
        raise ValueError("invalid profile evolve cli args")

    target = "user"
    summary = ""
    set_items: list[str] = []
    add_items: list[str] = []
    allow_soul = False
    dry_run = False
    i = 2
    while i < len(args):
        token = args[i]
        if token == "--target" and i + 1 < len(args):
            target = args[i + 1].strip() or target
            i += 2
            continue
        if token == "--summary" and i + 1 < len(args):
            summary = args[i + 1].strip()
            i += 2
            continue
        if token == "--set" and i + 1 < len(args):
            set_items.append(args[i + 1].strip())
            i += 2
            continue
        if token == "--add" and i + 1 < len(args):
            add_items.append(args[i + 1].strip())
            i += 2
            continue
        if token == "--allow-soul":
            allow_soul = True
            i += 1
            continue
        if token == "--dry-run":
            dry_run = True
            i += 1
            continue
        i += 1

    return {
        "target": target,
        "summary": summary,
        "set_items": set_items,
        "add_items": add_items,
        "allow_soul": allow_soul,
        "dry_run": dry_run,
    }


def _apply_profile_update_via_chat(*, plan: NLPlan) -> dict[str, object]:
    parsed = _parse_profile_evolve_cli_args(plan.cli_args)
    target = str(parsed.get("target", "user")).strip().lower()
    if target not in {"user", "soul", "both"}:
        target = "user"

    targets = ["user", "soul"] if target == "both" else [target]
    allow_soul = bool(parsed.get("allow_soul", False))
    if "soul" in targets and not allow_soul:
        # keep behavior safe/explicit: if soul is requested but not allowed by parser, skip soul.
        targets = [t for t in targets if t != "soul"]

    set_values = _parse_set_pairs(list(parsed.get("set_items", []) or []))
    add_values = _parse_add_pairs(list(parsed.get("add_items", []) or []))
    summary = str(parsed.get("summary", "") or "").strip()
    dry_run = bool(parsed.get("dry_run", False))
    root = resolve_workspace_root()

    updates: list[dict[str, object]] = []
    for current in targets:
        updates.append(
            apply_dialogue_profile_update(
                target=current,
                summary=summary,
                set_values=set_values,
                add_values=add_values,
                workspace_root=root,
                dry_run=dry_run,
            )
        )

    session = get_session_profile(force_reload=True)
    return {
        "applied": True,
        "target": target,
        "updates": updates,
        "profile": session.to_dict(),
    }


def _chat_execution_payload(
    *,
    message: str,
    session: SessionProfile,
    args: argparse.Namespace,
    plan: NLPlan | None = None,
) -> dict[str, object]:
    plan = plan or parse_nl_query(message, session=session)
    out: dict[str, object] = {"execution_plan": plan.to_dict()}
    if plan.intent == "profile":
        out["execution"] = {
            "return_code": 0,
            "note": "profile intent handled in chat mode; profile layers hot-reloaded",
        }
    elif plan.intent != "chat":
        nl_cmd = [os.environ.get("PYTHON", "python3"), "-m", "geoclaw_qgis.cli.main", "nl", message, "--execute"]
        if bool(getattr(args, "use_sre", False)):
            nl_cmd.extend(["--use-sre"])
        report_out = str(getattr(args, "sre_report_out", "") or "").strip()
        if report_out:
            nl_cmd.extend(["--sre-report-out", report_out])
        proc = subprocess.run(nl_cmd, check=False, capture_output=True, text=True)
        out["execution"] = {
            "command": nl_cmd,
            "return_code": int(proc.returncode),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    else:
        out["execution"] = {
            "return_code": 0,
            "note": "chat intent does not require workflow execution",
        }
    return out


def _chat_response_payload(
    *,
    message: str,
    session: SessionProfile,
    session_id: str = "",
    prefer_ai: bool = True,
    require_ai: bool = False,
    history_turns: list[dict[str, object]] | None = None,
    max_history_turns: int = 8,
) -> dict[str, object]:
    reply = ""
    mode = "fallback"
    ai_error = ""
    history_text = _chat_history_text(history_turns or [], max_turns=max_history_turns)
    profile_block = _profile_context_block(session)
    memory_context = _collect_chat_memory_context(message=message, session=session, session_id=session_id)
    memory_block = _chat_memory_context_block(memory_context)
    if prefer_ai:
        try:
            cfg = ExternalAIConfig.from_env()
            client = ExternalAIClient(cfg)
            system_prompt = (
                "You are GeoClaw chat assistant. "
                f"{GEOCLAW_IDENTITY.prompt_block()} "
                "Chat naturally and keep concise. "
                "Use profile and memory context to keep continuity and human-like personalization. "
                "Do not fabricate memory facts. "
                "If user request cannot be solved directly, provide actionable alternatives."
            )
            profile_prompt_block = f"[Profile Context]\n{profile_block}\n\n" if profile_block else ""
            memory_prompt_block = f"[Memory Context]\n{memory_block}\n\n" if memory_block else ""
            history_block = f"[Conversation History]\n{history_text}\n\n" if history_text else ""
            user_prompt = (
                f"{profile_prompt_block}"
                f"{memory_prompt_block}"
                f"{history_block}"
                f"User message: {message}\n"
                f"Preferred language: {session.user.preferred_language}\n"
                f"Preferred tone: {session.user.preferred_tone}"
            )
            reply = client.chat(user_prompt, system_prompt=system_prompt)
            mode = "ai"
        except Exception as exc:
            ai_error = str(exc)
            if bool(require_ai):
                raise RuntimeError(f"chat requires AI response, but AI call failed: {ai_error}") from exc
    if not reply.strip():
        if bool(require_ai):
            raise RuntimeError("chat requires AI response, but response content is empty")
        reply = _fallback_chat_reply(message, session, memory_context=memory_context)
    payload: dict[str, object] = {
        "mode": mode,
        "reply": reply,
        "suggestions": _chat_suggestions(message, session),
        "history_turns_used": min(len(history_turns or []), max(1, int(max_history_turns))),
        "memory_context": {
            "relevant_hits": len([x for x in (memory_context.get("relevant_hits") or []) if isinstance(x, dict)]),
            "recent_long_summaries": len(
                [x for x in (memory_context.get("recent_long_summaries") or []) if str(x).strip()]
            ),
            "daily_turns": int((memory_context.get("daily_digest") or {}).get("turn_count", 0) or 0)
            if isinstance(memory_context.get("daily_digest"), dict)
            else 0,
        },
    }
    if ai_error:
        payload["ai_warning"] = "AI response unavailable; fallback response is used."
    return payload


def cmd_chat(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    session = get_session_profile()
    message_opt = str(getattr(args, "message_opt", "") or "").strip()
    message_pos = " ".join(getattr(args, "message", []) or []).strip()
    message = message_opt or message_pos
    interactive = bool(getattr(args, "interactive", False))
    if not interactive and not message:
        raise ValueError("chat message is required unless --interactive is used")
    allow_no_ai = str(os.environ.get("GEOCLAW_ALLOW_NO_AI_CHAT", "")).strip().lower() in {"1", "true", "yes"}
    if bool(getattr(args, "no_ai", False)) and not allow_no_ai:
        raise ValueError("chat mode requires AI. '--no-ai' is disabled.")
    prefer_ai = True
    max_history_turns = max(1, int(getattr(args, "max_history_turns", 8)))

    session_id_raw = str(getattr(args, "session_id", "") or "").strip()
    use_session = interactive or bool(session_id_raw) or bool(getattr(args, "new_session", False))
    chat_session_payload: dict[str, object] | None = None
    chat_session_path: Path | None = None
    if use_session:
        if bool(getattr(args, "new_session", False)):
            sid = _normalize_chat_session_id(session_id_raw) or _new_chat_session_id()
            now = _utc_iso_now()
            chat_session_payload = {
                "session_id": sid,
                "created_at": now,
                "updated_at": now,
                "turns": [],
            }
            chat_session_path = _chat_session_path(sid)
        else:
            sid = _normalize_chat_session_id(session_id_raw) or (interactive and _new_chat_session_id()) or ""
            if sid:
                chat_session_payload, chat_session_path = _load_chat_session(sid)
    chat_memory_session_id = ""
    if isinstance(chat_session_payload, dict):
        chat_memory_session_id = str(chat_session_payload.get("session_id", "")).strip()
    if not chat_memory_session_id:
        chat_memory_session_id = _safe_chat_memory_session_id(session_id_raw)

    if interactive:
        pending: list[str] = [message] if message else []
        turn_count = 0
        final_rc = 0
        while True:
            if pending:
                current = pending.pop(0).strip()
            else:
                try:
                    current = input("You> ").strip()
                except EOFError:
                    break
            if not current:
                continue
            if current.lower() in _CHAT_EXIT_WORDS:
                break

            history_turns = []
            if isinstance(chat_session_payload, dict):
                turns = chat_session_payload.get("turns")
                if isinstance(turns, list):
                    history_turns = [x for x in turns if isinstance(x, dict)]

            plan = parse_nl_query(current, session=session)
            profile_update_payload: dict[str, object] | None = None
            if plan.intent == "profile":
                try:
                    profile_update_payload = _apply_profile_update_via_chat(plan=plan)
                    session = get_session_profile(force_reload=True)
                except Exception as exc:
                    profile_update_payload = {"applied": False, "error": str(exc)}

            payload = {
                "message": current,
                "intent": plan.intent,
                "nl_plan": plan.to_dict(),
                "chat": _chat_response_payload(
                    message=current,
                    session=session,
                    session_id=chat_memory_session_id,
                    prefer_ai=prefer_ai,
                    require_ai=not allow_no_ai,
                    history_turns=history_turns,
                    max_history_turns=max_history_turns,
                ),
                "profile_layers": {
                    "soul_path": session.soul_path,
                    "user_path": session.user_path,
                },
            }
            if profile_update_payload is not None:
                payload["profile_update"] = profile_update_payload
            if bool(getattr(args, "execute", False)):
                payload.update(_chat_execution_payload(message=current, session=session, args=args, plan=plan))
            payload["chat_memory"] = _record_chat_turn_memory(
                session=session,
                session_id=chat_memory_session_id,
                message=current,
                chat_payload=payload["chat"],
                intent=plan.intent,
            )

            print(f"GeoClaw> {payload['chat']['reply']}")
            turn_count += 1
            execution = payload.get("execution")
            if isinstance(execution, dict):
                final_rc = int(execution.get("return_code", final_rc))

            if isinstance(chat_session_payload, dict) and chat_session_path is not None:
                _append_chat_turn(chat_session_payload, message=current, chat=payload["chat"])
                _save_chat_session(chat_session_payload, chat_session_path)

        summary: dict[str, object] = {
            "interactive": True,
            "turns": turn_count,
            "profile_layers": {
                "soul_path": session.soul_path,
                "user_path": session.user_path,
            },
        }
        if isinstance(chat_session_payload, dict) and chat_session_path is not None:
            turns = chat_session_payload.get("turns")
            summary["session"] = {
                "session_id": str(chat_session_payload.get("session_id", "")),
                "turns": len(turns) if isinstance(turns, list) else 0,
                "path": str(chat_session_path),
            }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return int(final_rc)

    history_turns = []
    if isinstance(chat_session_payload, dict):
        turns = chat_session_payload.get("turns")
        if isinstance(turns, list):
            history_turns = [x for x in turns if isinstance(x, dict)]

    payload = {
        "message": message,
        "intent": "",
        "chat": _chat_response_payload(
            message=message,
            session=session,
            session_id=chat_memory_session_id,
            prefer_ai=prefer_ai,
            require_ai=not allow_no_ai,
            history_turns=history_turns,
            max_history_turns=max_history_turns,
        ),
        "profile_layers": {
            "soul_path": session.soul_path,
            "user_path": session.user_path,
        },
    }
    plan = parse_nl_query(message, session=session)
    payload["intent"] = plan.intent
    payload["nl_plan"] = plan.to_dict()
    profile_update_payload: dict[str, object] | None = None
    if plan.intent == "profile":
        try:
            profile_update_payload = _apply_profile_update_via_chat(plan=plan)
            session = get_session_profile(force_reload=True)
            payload["profile_layers"] = {
                "soul_path": session.soul_path,
                "user_path": session.user_path,
            }
            payload["chat"] = _chat_response_payload(
                message=message,
                session=session,
                session_id=chat_memory_session_id,
                prefer_ai=prefer_ai,
                require_ai=not allow_no_ai,
                history_turns=history_turns,
                max_history_turns=max_history_turns,
            )
        except Exception as exc:
            profile_update_payload = {"applied": False, "error": str(exc)}
    if profile_update_payload is not None:
        payload["profile_update"] = profile_update_payload
    if bool(getattr(args, "execute", False)):
        payload.update(_chat_execution_payload(message=message, session=session, args=args, plan=plan))
    payload["chat_memory"] = _record_chat_turn_memory(
        session=session,
        session_id=chat_memory_session_id,
        message=message,
        chat_payload=payload["chat"],
        intent=plan.intent,
    )

    if isinstance(chat_session_payload, dict) and chat_session_path is not None:
        _append_chat_turn(chat_session_payload, message=message, chat=payload["chat"])
        _save_chat_session(chat_session_payload, chat_session_path)
        turns = chat_session_payload.get("turns")
        payload["session"] = {
            "session_id": str(chat_session_payload.get("session_id", "")),
            "turns": len(turns) if isinstance(turns, list) else 0,
            "path": str(chat_session_path),
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    execution = payload.get("execution")
    if isinstance(execution, dict):
        return int(execution.get("return_code", 0))
    return 0


def cmd_local(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    command_text = str(args.cmd or "").strip()
    if not command_text:
        raise ValueError("--cmd is required")
    cwd_text = str(args.cwd or "").strip()
    workdir = Path(cwd_text).expanduser().resolve() if cwd_text else Path.cwd().resolve()
    if not workdir.exists() or not workdir.is_dir():
        raise ValueError(f"--cwd is not a valid directory: {workdir}")

    start_ts = time.time()
    timed_out = False
    try:
        if bool(args.shell):
            proc = subprocess.run(
                command_text,
                cwd=str(workdir),
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(1, int(args.timeout)),
            )
        else:
            cmd = shlex.split(command_text)
            if not cmd:
                raise ValueError("--cmd produced empty token list")
            proc = subprocess.run(
                cmd,
                cwd=str(workdir),
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(1, int(args.timeout)),
            )
        return_code = int(proc.returncode)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        return_code = 124
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")

    elapsed = round(time.time() - start_ts, 3)
    payload = {
        "command": command_text,
        "cwd": str(workdir),
        "shell": bool(args.shell),
        "timeout": int(args.timeout),
        "timed_out": timed_out,
        "return_code": return_code,
        "elapsed_seconds": elapsed,
        "stdout": stdout,
        "stderr": stderr,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return int(return_code)


def resolve_workspace_root() -> Path:
    candidates: list[Path] = [Path.cwd().resolve()]
    env_workspace = os.environ.get("GEOCLAW_OPENAI_WORKSPACE", "").strip()
    if env_workspace:
        candidates.append(Path(env_workspace).expanduser().resolve())

    cfg = read_config()
    defaults = cfg.get("defaults") if isinstance(cfg.get("defaults"), dict) else {}
    cfg_workspace = str(defaults.get("workspace", "")).strip() if defaults else ""
    if cfg_workspace:
        candidates.append(Path(cfg_workspace).expanduser().resolve())

    seen: set[str] = set()
    for item in candidates:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        if (item / "scripts").is_dir():
            return item
    return Path.cwd().resolve()


def build_runner_cmd(script_name: str) -> list[str]:
    root = resolve_workspace_root()
    runner = root / "scripts" / script_name
    if not runner.exists():
        raise FileNotFoundError(f"runner not found in workspace: {runner}")
    return [os.environ.get("PYTHON", "python3"), str(runner)]


def run_checked(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {shlex.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc.stdout.strip()


def cmd_update(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    root = resolve_workspace_root()
    if not (root / ".git").exists():
        raise RuntimeError(f"workspace is not a git repository: {root}")

    remote_ref = f"{args.remote}/{args.branch}"
    fetch_proc = subprocess.run(
        ["git", "fetch", args.remote, args.branch],
        cwd=str(root),
        check=False,
        capture_output=True,
        text=True,
    )
    fetch_ok = fetch_proc.returncode == 0
    fetch_warning = ""
    if not fetch_ok:
        fetch_warning = (fetch_proc.stderr or fetch_proc.stdout).strip() or "git fetch failed"

    local_head = run_checked(["git", "rev-parse", "HEAD"], root)
    remote_head = ""
    ahead = 0
    behind = 0
    try:
        remote_head = run_checked(["git", "rev-parse", remote_ref], root)
        counts = run_checked(["git", "rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"], root)
        parts = counts.split()
        if len(parts) == 2:
            ahead = int(parts[0])
            behind = int(parts[1])
    except Exception:
        remote_head = ""
        ahead = 0
        behind = 0

    status_payload: dict[str, object] = {
        "workspace": str(root),
        "remote": args.remote,
        "branch": args.branch,
        "local_head": local_head,
        "remote_head": remote_head,
        "ahead": ahead,
        "behind": behind,
        "fetch_ok": fetch_ok,
        "update_available": bool(remote_head) and behind > 0,
        "up_to_date": bool(remote_head) and behind == 0,
        "pulled": False,
        "reinstalled": False,
    }
    if fetch_warning:
        status_payload["warning"] = f"fetch_failed: {fetch_warning}"

    if args.check_only or not remote_head or behind == 0:
        print(json.dumps(status_payload, ensure_ascii=False, indent=2))
        return 0
    if not fetch_ok:
        status_payload["warning"] = "fetch_failed; skip pull in this run"
        print(json.dumps(status_payload, ensure_ascii=False, indent=2))
        return 0

    dirty = run_checked(["git", "status", "--porcelain"], root)
    if dirty and not args.force:
        raise RuntimeError("workspace has uncommitted changes; commit/stash or use --force")

    pull_cmd = ["git", "pull", "--ff-only", args.remote, args.branch]
    if args.rebase:
        pull_cmd = ["git", "pull", "--rebase", args.remote, args.branch]
    pull_proc = subprocess.run(pull_cmd, cwd=str(root), check=False, capture_output=True, text=True)
    if pull_proc.returncode != 0:
        raise RuntimeError(
            f"git pull failed ({pull_proc.returncode})\n"
            f"stdout:\n{pull_proc.stdout}\n"
            f"stderr:\n{pull_proc.stderr}"
        )
    status_payload["pulled"] = True
    status_payload["pull_stdout"] = pull_proc.stdout.strip()

    if not args.skip_install:
        python_bin = os.environ.get("PYTHON", sys.executable or "python3")
        install_cmd = [python_bin, "-m", "pip", "install", "--user", "--break-system-packages", "-e", str(root)]
        install_proc = subprocess.run(install_cmd, cwd=str(root), check=False, capture_output=True, text=True)
        if install_proc.returncode != 0:
            raise RuntimeError(
                f"editable install failed ({install_proc.returncode})\n"
                f"stdout:\n{install_proc.stdout}\n"
                f"stderr:\n{install_proc.stderr}"
            )
        status_payload["reinstalled"] = True
        status_payload["install_stdout"] = install_proc.stdout.strip()

    print(json.dumps(status_payload, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_status(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    store = TaskMemoryStore(session_profile=get_session_profile())
    payload = {
        "memory_root": str(store.short_dir.parent),
        "short_count": store.count_short(),
        "long_count": store.count_long(),
        "short_dir": str(store.short_dir),
        "archive_short_dir": str(store.archive_short_dir),
        "long_file": str(store.long_file),
        "limit": args.limit,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_short(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    store = TaskMemoryStore(session_profile=get_session_profile())
    rows = store.list_short(limit=args.limit, status=args.status)
    print(json.dumps({"items": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_long(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    store = TaskMemoryStore(session_profile=get_session_profile())
    rows = store.list_long(limit=args.limit)
    print(json.dumps({"items": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_review(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    store = TaskMemoryStore(session_profile=get_session_profile())
    payload = store.review_task_to_long(
        args.task_id,
        summary=args.summary or "",
        lessons=args.lesson or [],
        next_actions=args.action or [],
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_archive(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    store = TaskMemoryStore(session_profile=get_session_profile())
    payload = store.archive_short(
        before_days=args.before_days,
        status=args.status,
        include_running=bool(args.include_running),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_search(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    if not args.query.strip():
        raise ValueError("--query is required")
    store = TaskMemoryStore(session_profile=get_session_profile())
    rows = store.search_memory(
        query=args.query,
        scope=args.scope,
        top_k=args.top_k,
        min_score=args.min_score,
    )
    print(json.dumps({"items": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def _task_type_from_plan(plan: NLPlan) -> str:
    if plan.intent == "network":
        return "trajectory_analysis"
    if plan.intent == "operator":
        return "proximity_analysis"
    if plan.intent == "skill":
        joined = " ".join(plan.cli_args).lower()
        if "site" in joined or "mall" in joined or "选址" in joined:
            return "site_selection"
        return "spatial_comparison"
    if plan.intent == "run":
        args = list(plan.cli_args)
        if "--case" in args:
            idx = args.index("--case")
            if idx + 1 < len(args):
                case = args[idx + 1]
                if case == "site_selection":
                    return "site_selection"
                if case == "location_analysis":
                    return "proximity_analysis"
                if case == "wuhan_advanced":
                    return "spatial_comparison"
        return "spatial_comparison"
    return "spatial_comparison"


def _extract_path_hints(text: str) -> list[str]:
    out: list[str] = []
    for raw in _PATH_HINT_RE.findall(text):
        p = str(raw).strip()
        if p and p not in out:
            out.append(p)
    return out


def _extract_flag_value(cli_args: list[str], flag: str) -> str:
    if flag not in cli_args:
        return ""
    idx = cli_args.index(flag)
    if idx + 1 >= len(cli_args):
        return ""
    return str(cli_args[idx + 1]).strip()


def _extract_flag_values(cli_args: list[str], flag: str) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(cli_args)
    while i < n:
        token = str(cli_args[i])
        if token == flag and i + 1 < n:
            value = str(cli_args[i + 1]).strip()
            if value:
                out.append(value)
            i += 2
            continue
        i += 1
    return out


def _remove_flag_with_value(cli_args: list[str], flag: str) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(cli_args)
    while i < n:
        token = str(cli_args[i])
        if token == flag:
            i += 2
            continue
        out.append(token)
        i += 1
    return out


def _remove_flag(cli_args: list[str], flag: str) -> list[str]:
    return [str(x) for x in cli_args if str(x) != flag]


def _ensure_flag_with_value(cli_args: list[str], flag: str, value: str) -> list[str]:
    out = _remove_flag_with_value(cli_args, flag)
    out.extend([flag, value])
    return out


def _enforce_nl_route_constraints(
    *,
    plan: NLPlan,
    routed_cli_args: list[str],
    route_notes: list[str],
) -> list[str]:
    args = [str(x) for x in routed_cli_args if str(x).strip()]
    base = [str(x) for x in plan.cli_args if str(x).strip()]
    if not args:
        return args

    if plan.intent == "run" and args[0] == "run":
        for source_flag in _RUN_SOURCE_FLAGS:
            source_value = _extract_flag_value(base, source_flag)
            if source_value:
                for remove_flag in _RUN_SOURCE_FLAGS:
                    args = _remove_flag_with_value(args, remove_flag)
                args.extend([source_flag, source_value])
                route_notes.append(f"Preserved explicit input source from NL plan: {source_flag}={source_value}.")
                break

        for value_flag in _RUN_VALUE_FLAGS:
            value = _extract_flag_value(base, value_flag)
            if value:
                current = _extract_flag_value(args, value_flag)
                if current != value:
                    args = _ensure_flag_with_value(args, value_flag, value)
                    route_notes.append(f"Preserved explicit NL parameter: {value_flag}={value}.")

        for bool_flag in _RUN_BOOL_FLAGS:
            if bool_flag in base and bool_flag not in args:
                args.append(bool_flag)
                route_notes.append(f"Preserved explicit NL switch: {bool_flag}.")

    if plan.intent == "network" and args[0] == "network":
        for value_flag in ("--pfs-csv", "--out-dir", "--sep", "--index-col", "--tz", "--crs", "--columns-map"):
            value = _extract_flag_value(base, value_flag)
            if value:
                current = _extract_flag_value(args, value_flag)
                if current != value:
                    args = _ensure_flag_with_value(args, value_flag, value)
                    route_notes.append(f"Preserved explicit NL parameter: {value_flag}={value}.")
        if "--dry-run" in base and "--dry-run" not in args:
            args.append("--dry-run")
            route_notes.append("Preserved explicit NL switch: --dry-run.")

    if plan.intent == "operator" and args[0] == "operator":
        algo = _extract_flag_value(base, "--algorithm")
        if algo:
            current_algo = _extract_flag_value(args, "--algorithm")
            if current_algo != algo:
                args = _ensure_flag_with_value(args, "--algorithm", algo)
                route_notes.append(f"Preserved explicit NL parameter: --algorithm={algo}.")

        for repeat_flag in ("--param", "--param-json"):
            values = _extract_flag_values(base, repeat_flag)
            if values:
                args = _remove_flag_with_value(args, repeat_flag)
                for value in values:
                    args.extend([repeat_flag, value])
                route_notes.append(f"Preserved explicit NL parameter list: {repeat_flag} ({len(values)} items).")

        for value_flag in ("--params-file", "--step-id", "--qgis-process"):
            value = _extract_flag_value(base, value_flag)
            if value:
                current = _extract_flag_value(args, value_flag)
                if current != value:
                    args = _ensure_flag_with_value(args, value_flag, value)
                    route_notes.append(f"Preserved explicit NL parameter: {value_flag}={value}.")

        if "--dry-run" in base and "--dry-run" not in args:
            args.append("--dry-run")
            route_notes.append("Preserved explicit NL switch: --dry-run.")

    return args


def _load_dataset_specs_file(path_text: str) -> list[dict[str, object]]:
    if not path_text.strip():
        return []
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"datasets-file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("datasets")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []


def _collect_reasoning_datasets(
    *,
    query_text: str,
    data_dir: str = "",
    datasets_file: str = "",
) -> list[dict[str, object]]:
    specs = _load_dataset_specs_file(datasets_file)

    discovered: list[dict[str, object]] = []
    if data_dir.strip():
        discovered.extend(discover_datasets_from_dir(data_dir))

    for raw in _extract_path_hints(query_text):
        p = Path(raw).expanduser().resolve()
        if p.exists() and p.is_file():
            try:
                discovered.append(dataset_spec_from_path(p))
            except Exception:
                continue
        elif p.exists() and p.is_dir():
            try:
                discovered.extend(discover_datasets_from_dir(p))
            except Exception:
                continue

    return merge_dataset_specs(base=specs, extra=discovered)


def _apply_sre_task_route(routed_cli_args: list[str], task_type: str, route_notes: list[str]) -> list[str]:
    args = list(routed_cli_args)
    if not args:
        return args
    if args[0] != "run":
        return args

    case_map = {
        "site_selection": "site_selection",
        "proximity_analysis": "location_analysis",
        "accessibility_analysis": "location_analysis",
        "change_detection": "wuhan_advanced",
    }
    mapped = case_map.get(task_type, "")
    if not mapped:
        return args
    if "--case" not in args:
        return args
    idx = args.index("--case")
    if idx + 1 >= len(args):
        return args
    prev_case = args[idx + 1]
    if prev_case != mapped:
        args[idx + 1] = mapped
        route_notes.append(f"SRE remapped run case: {prev_case} -> {mapped}.")
    return args


def _apply_sre_execution_plan(
    routed_cli_args: list[str],
    *,
    sre_payload: dict[str, object] | None,
    base_intent: str = "",
    route_notes: list[str],
) -> tuple[list[str], bool]:
    if not isinstance(sre_payload, dict):
        return routed_cli_args, False
    execution = sre_payload.get("execution_plan")
    if not isinstance(execution, dict):
        return routed_cli_args, False
    if not bool(execution.get("safe_to_execute", False)):
        reasons = execution.get("blocking_reasons")
        if isinstance(reasons, list) and reasons:
            route_notes.append(
                "SRE execution plan blocked: " + "; ".join(str(x).strip() for x in reasons if str(x).strip())
            )
        else:
            route_notes.append("SRE execution plan is not safe_to_execute; keep current route.")
        return routed_cli_args, False
    cmd = execution.get("command")
    if not isinstance(cmd, list):
        return routed_cli_args, False
    safe_cmd = [str(x).strip() for x in cmd if str(x).strip()]
    if not safe_cmd:
        return routed_cli_args, False
    if safe_cmd[0] not in _SRE_ALLOWED_ROOT_COMMANDS:
        route_notes.append(f"SRE execution plan rejected unsupported root command: {safe_cmd[0]}")
        return routed_cli_args, False
    if not _is_sre_route_compatible(base_intent=base_intent, new_root=safe_cmd[0]):
        route_notes.append(
            f"SRE execution plan rejected cross-intent reroute: intent={base_intent} -> root={safe_cmd[0]}"
        )
        return routed_cli_args, False
    ok, reason = _validate_sre_command_shape(safe_cmd)
    if not ok:
        route_notes.append(f"SRE execution plan rejected invalid command shape: {reason}")
        return routed_cli_args, False
    route_notes.append(f"SRE execution plan applied: route_target={execution.get('route_target', '')}.")
    return safe_cmd, True


def cmd_reasoning(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    session = get_session_profile()
    query_text = " ".join(args.query).strip()
    if not query_text:
        raise ValueError("query text is required")

    _set_reasoner_env_overrides(
        mode=getattr(args, "reasoner_mode", "") or "",
        retries=getattr(args, "llm_retries", None),
        strict_external=bool(getattr(args, "strict_external", False)),
    )

    datasets = _collect_reasoning_datasets(
        query_text=query_text,
        data_dir=args.data_dir or "",
        datasets_file=args.datasets_file or "",
    )
    input_data = build_reasoning_input_from_profile(
        query=query_text,
        session=session,
        datasets=datasets,
        planner_hints={
            "candidate_task_type": args.planner_task or "",
            "candidate_methods": args.planner_method or [],
        },
        project_context={
            "study_area": args.project_study_area or "",
            "default_crs": args.project_crs or "",
            "analysis_goal": args.project_goal or "",
        },
    )
    result = run_spatial_reasoning(input_data)
    payload = {
        "input": input_data.to_dict(),
        "result": result.to_dict(),
        "profile_layers": {
            "soul_path": session.soul_path,
            "user_path": session.user_path,
        },
    }

    report_md = ""
    if bool(args.report_out) or bool(args.print_report):
        report_md = render_reasoning_report(input_data=input_data, result=result)

    if bool(args.report_out):
        workspace_root = resolve_workspace_root()
        try:
            validate_output_targets(
                {"OUTPUT": str(args.report_out)},
                workspace_root=workspace_root,
                safe_output_root=fixed_output_root(workspace_root),
            )
        except OutputSecurityError as exc:
            raise RuntimeError(f"reasoning report output security check failed: {exc}") from exc

        report_path = Path(str(args.report_out)).expanduser()
        if not report_path.is_absolute():
            report_path = (workspace_root / report_path).resolve()
        else:
            report_path = report_path.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_md, encoding="utf-8")
        payload["report"] = {
            "path": str(report_path),
            "format": "markdown",
            "size_bytes": len(report_md.encode("utf-8")),
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if bool(args.print_report):
        print("\n# --- Reasoning Report (Markdown) ---\n")
        print(report_md)
    if args.strict and result.validation.status == "fail":
        return 1
    return 0


def cmd_nl(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    query_text = " ".join(args.query).strip()
    if not query_text:
        raise ValueError("query text is required")

    session = get_session_profile()
    plan: NLPlan = parse_nl_query(query_text, session=session)
    if plan.intent == "chat":
        chat_payload = _chat_response_payload(
            message=query_text,
            session=session,
            session_id="nl_preview",
            prefer_ai=True,
            require_ai=True,
        )
        payload = {
            "query": plan.query,
            "intent": plan.intent,
            "confidence": plan.confidence,
            "reasons": plan.reasons,
            "command_preview": "geoclaw-openai chat --message " + query_text,
            "cli_args": ["chat", "--message", query_text],
            "chat": chat_payload,
            "profile_layers": {
                "soul_path": session.soul_path,
                "user_path": session.user_path,
            },
            "execute": False,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    routed_cli_args = list(plan.cli_args)
    route_notes: list[str] = []
    sre_input_data = None
    sre_result = None
    locked_cli_args: list[str] | None = None
    query_lower = query_text.lower()
    if plan.intent in {"run", "operator"} and any(k in query_lower for k in ("mall", "shopping", "商场")):
        source_city = _extract_flag_value(plan.cli_args, "--city")
        source_bbox = _extract_flag_value(plan.cli_args, "--bbox")
        source_data_dir = _extract_flag_value(plan.cli_args, "--data-dir")
        has_explicit_source = bool(source_city or source_bbox or source_data_dir)
        allow_skill_route = not has_explicit_source
        if allow_skill_route:
            preferred = "mall_site_selection_qgis"
            if any(k in query_lower for k in ("llm", "ai", "大模型")):
                preferred = "mall_site_selection_llm"
            routed_cli_args = ["skill", "--", "--skill", preferred]
            top_n = _extract_flag_value(plan.cli_args, "--top-n")
            if top_n and preferred == "mall_site_selection_qgis":
                routed_cli_args.extend(["--set", f"top_n={top_n}"])
                route_notes.append(f"Preserved NL top-n for skill pipeline: top_n={top_n}.")
            if "--skip-download" in plan.cli_args and preferred == "mall_site_selection_qgis":
                routed_cli_args.append("--skip-download")
            locked_cli_args = list(routed_cli_args)
            route_notes.append(f"Tool router prioritized registered skill={preferred} by soul execution hierarchy.")
        else:
            locked_cli_args = list(plan.cli_args)
            route_notes.append(
                "Detected explicit input source; keep native run route to preserve requested study area."
            )

    sre_payload: dict[str, object] | None = None
    if bool(args.use_sre) and plan.intent in _SRE_SPATIAL_INTENTS:
        try:
            _set_reasoner_env_overrides(
                mode=getattr(args, "sre_reasoner_mode", "") or "",
                retries=getattr(args, "sre_llm_retries", None),
                strict_external=bool(getattr(args, "sre_strict_external", False)),
            )
            datasets = _collect_reasoning_datasets(
                query_text=query_text,
                data_dir=args.sre_data_dir or "",
                datasets_file=args.sre_datasets_file or "",
            )
            input_data = build_reasoning_input_from_profile(
                query=query_text,
                session=session,
                datasets=datasets,
                planner_hints={
                    "candidate_task_type": _task_type_from_plan(plan),
                    "candidate_methods": [],
                },
                project_context={
                    "analysis_goal": "nl_command_planning",
                },
            )
            sre_input_data = input_data
            sre_result = run_spatial_reasoning(input_data)
            sre_payload = sre_result.to_dict()
            req = list(sre_result.validation.required_preconditions or [])
            rev = list(sre_result.validation.revisions_applied or [])
            if req:
                route_notes.append("SRE required_preconditions: " + ", ".join(req))
            if rev:
                route_notes.append("SRE revisions_applied: " + ", ".join(rev))
            routed_cli_args, execution_plan_applied = _apply_sre_execution_plan(
                routed_cli_args,
                sre_payload=sre_payload,
                base_intent=plan.intent,
                route_notes=route_notes,
            )
            if not execution_plan_applied:
                routed_cli_args = _apply_sre_task_route(routed_cli_args, sre_result.task_profile.task_type, route_notes)
            else:
                route_notes.append("SRE execution plan took precedence over legacy task route remapping.")
            if locked_cli_args is not None and routed_cli_args != locked_cli_args:
                routed_cli_args = list(locked_cli_args)
                route_notes.append(
                    "Kept explicit NL-prioritized route; rejected conflicting SRE reroute."
                )
            if args.sre_strict and sre_result.validation.status == "fail":
                route_notes.append("SRE strict mode blocked execution because validation status=fail.")
        except Exception as exc:
            if args.sre_strict:
                raise
            route_notes.append(f"SRE disabled due to non-blocking error: {exc}")
    elif bool(args.use_sre):
        route_notes.append(f"SRE skipped for non-spatial intent={plan.intent}.")

    routed_cli_args = _enforce_nl_route_constraints(
        plan=plan,
        routed_cli_args=routed_cli_args,
        route_notes=route_notes,
    )

    nl_report_md = ""
    nl_report_meta: dict[str, object] | None = None
    if bool(getattr(args, "sre_report_out", "")) or bool(getattr(args, "sre_print_report", False)):
        if not bool(args.use_sre):
            raise RuntimeError("NL SRE report requires --use-sre.")
        if sre_input_data is None or sre_result is None:
            raise RuntimeError("NL SRE report requires spatial intent and successful SRE result.")
        nl_report_md = render_reasoning_report(input_data=sre_input_data, result=sre_result)

        report_out = str(getattr(args, "sre_report_out", "") or "").strip()
        if report_out:
            workspace_root = resolve_workspace_root()
            try:
                validate_output_targets(
                    {"OUTPUT": report_out},
                    workspace_root=workspace_root,
                    safe_output_root=fixed_output_root(workspace_root),
                )
            except OutputSecurityError as exc:
                raise RuntimeError(f"nl sre report output security check failed: {exc}") from exc

            report_path = Path(report_out).expanduser()
            if not report_path.is_absolute():
                report_path = (workspace_root / report_path).resolve()
            else:
                report_path = report_path.resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(nl_report_md, encoding="utf-8")
            nl_report_meta = {
                "path": str(report_path),
                "format": "markdown",
                "size_bytes": len(nl_report_md.encode("utf-8")),
            }

    payload = {
        "query": plan.query,
        "intent": plan.intent,
        "confidence": plan.confidence,
        "reasons": plan.reasons,
        "command_preview": "geoclaw-openai " + " ".join(routed_cli_args),
        "cli_args": routed_cli_args,
        "tool_route_notes": route_notes,
        "profile_layers": {
            "soul_path": session.soul_path,
            "user_path": session.user_path,
        },
        "sre_enabled": bool(args.use_sre),
        "sre": sre_payload,
        "execute": bool(args.execute),
    }
    if nl_report_meta is not None:
        payload["sre_report"] = nl_report_meta
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if bool(getattr(args, "sre_print_report", False)):
        print("\n# --- NL SRE Report (Markdown) ---\n")
        print(nl_report_md)

    if bool(args.use_sre) and bool(args.sre_strict):
        if isinstance(sre_payload, dict):
            validation = sre_payload.get("validation")
            if isinstance(validation, dict) and str(validation.get("status", "")).strip().lower() == "fail":
                return 1

    if not args.execute:
        print("[NL] 预览模式：加 --execute 将执行上述命令。")
        return 0

    current_cli = Path(sys.argv[0]).expanduser()
    if current_cli.exists() and current_cli.is_file() and "geoclaw-openai" in current_cli.name:
        cmd = [str(current_cli), *routed_cli_args]
    else:
        cmd = [os.environ.get("PYTHON", "python3"), "-m", "geoclaw_qgis.cli.main", *routed_cli_args]
    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def cmd_skill(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    cmd = build_runner_cmd("geoclaw_skill_runner.py")

    extra = list(args.extra)
    if extra and extra[0] == "--":
        extra = extra[1:]

    cmd.extend(extra)
    return os.spawnvp(os.P_WAIT, cmd[0], cmd)


def _append_skill_guard_log(event: dict[str, object]) -> None:
    sec_dir = geoclaw_home() / "security"
    sec_dir.mkdir(parents=True, exist_ok=True)
    log_file = sec_dir / "skill_guard_log.jsonl"
    row = dict(event)
    row["ts"] = dt.datetime.now(dt.timezone.utc).isoformat()
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _resolve_registry_path(path_text: str) -> Path:
    root = resolve_workspace_root()
    raw = (path_text or os.environ.get("GEOCLAW_OPENAI_SKILL_REGISTRY", DEFAULT_REGISTRY)).strip() or DEFAULT_REGISTRY
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (root / path).resolve()
    return path


def _confirm_skill_registration(*, confirmed_flag: bool) -> bool:
    confirmed = bool(confirmed_flag)
    if confirmed:
        return True
    if not sys.stdin.isatty():
        raise ValueError("--confirm is required in non-interactive mode.")
    answer = input("Assessment complete. Type YES to confirm registration: ").strip()
    return answer == "YES"


def _assert_skill_risk_allowed(
    *,
    assessment: dict[str, object],
    allow_high_risk: bool,
    blocked_action: str,
    spec_file: Path,
    registry_path: Path,
) -> None:
    if assessment.get("risk_level") == "high" and not allow_high_risk:
        _append_skill_guard_log(
            {
                "action": blocked_action,
                "spec_file": str(spec_file),
                "registry": str(registry_path),
                "assessment": assessment,
                "reason": "high_risk_requires_allow_high_risk",
            }
        )
        raise RuntimeError(
            "Skill assessment risk_level=high. Registration blocked. "
            "Review findings and use --allow-high-risk with explicit confirmation if you still want to proceed."
        )


def cmd_skill_registry_assess(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    root = resolve_workspace_root()
    spec_path = Path(args.spec_file).expanduser().resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"skill spec file not found: {spec_path}")

    spec = load_skill_spec_file(spec_path)
    report = assess_skill_spec(spec, workspace_root=root)
    payload = {
        "spec_file": str(spec_path),
        "workspace": str(root),
        "registry": str(_resolve_registry_path(args.registry)),
        "assessment": report,
    }
    _append_skill_guard_log({"action": "assess", **payload})
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_skill_registry_register(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    root = resolve_workspace_root()
    spec_path = Path(args.spec_file).expanduser().resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"skill spec file not found: {spec_path}")

    spec = load_skill_spec_file(spec_path)
    assessment = assess_skill_spec(spec, workspace_root=root)
    registry_path = _resolve_registry_path(args.registry)

    _assert_skill_risk_allowed(
        assessment=assessment,
        allow_high_risk=bool(args.allow_high_risk),
        blocked_action="register_blocked",
        spec_file=spec_path,
        registry_path=registry_path,
    )

    confirmed = _confirm_skill_registration(confirmed_flag=bool(args.confirm))
    if not confirmed:
        print(json.dumps({"registered": False, "reason": "user_not_confirmed", "assessment": assessment}, ensure_ascii=False, indent=2))
        return 1

    result = upsert_skill_registry(registry_path, skill_spec=spec, replace=bool(args.replace))
    payload = {
        "registered": True,
        "spec_file": str(spec_path),
        "registry": str(registry_path),
        "assessment": assessment,
        "result": result,
    }
    _append_skill_guard_log({"action": "register", **payload})
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_skill_registry_import_openclaw(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    root = resolve_workspace_root()
    spec_path = Path(args.spec_file).expanduser().resolve()
    if not spec_path.exists():
        raise FileNotFoundError(f"openclaw spec file not found: {spec_path}")

    spec = load_openclaw_skill_spec(spec_path, id_prefix=str(args.id_prefix or "openclaw_"))
    assessment = assess_skill_spec(spec, workspace_root=root)
    registry_path = _resolve_registry_path(args.registry)
    payload: dict[str, object] = {
        "imported": True,
        "source": "openclaw",
        "spec_file": str(spec_path),
        "registry": str(registry_path),
        "workspace": str(root),
        "converted_spec": spec,
        "assessment": assessment,
    }

    if bool(args.dry_run):
        payload["registered"] = False
        payload["dry_run"] = True
        _append_skill_guard_log({"action": "import_openclaw_dry_run", **payload})
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    _assert_skill_risk_allowed(
        assessment=assessment,
        allow_high_risk=bool(args.allow_high_risk),
        blocked_action="import_openclaw_blocked",
        spec_file=spec_path,
        registry_path=registry_path,
    )
    confirmed = _confirm_skill_registration(confirmed_flag=bool(args.confirm))
    if not confirmed:
        payload["registered"] = False
        payload["reason"] = "user_not_confirmed"
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    result = upsert_skill_registry(registry_path, skill_spec=spec, replace=bool(args.replace))
    payload["registered"] = True
    payload["result"] = result
    _append_skill_guard_log({"action": "import_openclaw", **payload})
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    cmd = build_runner_cmd("geoclaw_case_runner.py")
    cmd.extend(["--case", args.case])

    if args.city:
        cmd.extend(["--city", args.city])
    if args.bbox:
        cmd.extend(["--bbox", args.bbox])
    if args.data_dir:
        cmd.extend(["--data-dir", args.data_dir])
    if args.tag:
        cmd.extend(["--tag", args.tag])
    if args.raw_dir:
        cmd.extend(["--raw-dir", args.raw_dir])
    if args.out_root:
        cmd.extend(["--out-root", args.out_root])
    if args.top_n is not None:
        cmd.extend(["--top-n", str(args.top_n)])
    if args.timeout is not None:
        cmd.extend(["--timeout", str(args.timeout)])
    if args.skip_download:
        cmd.append("--skip-download")
    if args.force_download:
        cmd.append("--force-download")
    if args.with_maps:
        cmd.append("--with-maps")
    if args.no_maps:
        cmd.append("--no-maps")
    if args.qgis_python:
        cmd.extend(["--qgis-python", args.qgis_python])

    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def cmd_operator(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    cmd = build_runner_cmd("geoclaw_operator_runner.py")

    if args.algorithm:
        cmd.extend(["--algorithm", args.algorithm])
    if args.qgis_process:
        cmd.extend(["--qgis-process", args.qgis_process])
    if args.step_id:
        cmd.extend(["--step-id", args.step_id])
    for item in args.param:
        cmd.extend(["--param", item])
    for item in args.param_json:
        cmd.extend(["--param-json", item])
    if args.params_file:
        cmd.extend(["--params-file", args.params_file])
    if args.dry_run:
        cmd.append("--dry-run")

    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def cmd_network(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    svc = TrackintelNetworkService()

    columns_map: dict[str, str] | None = None
    if args.columns_map:
        try:
            parsed = json.loads(args.columns_map)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--columns-map must be valid JSON mapping: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("--columns-map must decode to a JSON object")
        columns_map = {str(k): str(v) for k, v in parsed.items()}

    workspace_root = resolve_workspace_root()
    try:
        validate_output_targets(
            {
                "INPUT": str(Path(args.pfs_csv).expanduser().resolve()),
                "OUTPUT": args.out_dir,
            },
            workspace_root=workspace_root,
            safe_output_root=fixed_output_root(workspace_root),
        )
    except OutputSecurityError as exc:
        raise RuntimeError(f"network output security check failed: {exc}") from exc

    try:
        payload = svc.run_from_positionfixes_csv(
            pfs_csv=args.pfs_csv,
            out_dir=args.out_dir,
            sep=args.sep,
            index_col=args.index_col,
            tz=args.tz,
            crs=args.crs,
            columns_map=columns_map,
            staypoint_dist_threshold=args.staypoint_dist_threshold,
            staypoint_time_threshold=args.staypoint_time_threshold,
            gap_threshold=args.gap_threshold,
            activity_time_threshold=args.activity_time_threshold,
            location_epsilon=args.location_epsilon,
            location_min_samples=args.location_min_samples,
            location_agg_level=args.location_agg_level,
            dry_run=args.dry_run,
        )
    except TrackintelIntegrationError as exc:
        raise RuntimeError(
            f"{exc}\n"
            "Install optional deps: pip install 'geoclaw-openai[network]' "
            "or pip install trackintel networkx pandas."
        ) from exc

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geoclaw-openai",
        description=f"{PROJECT_NAME} CLI ({LAB_AFFILIATION})",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROJECT_NAME} {PROJECT_VERSION} | {LAB_AFFILIATION}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    onboard = sub.add_parser("onboard", help="setup GeoClaw runtime and API parameters")
    onboard.add_argument("--api-key", default="", help="AI API key (OpenAI/Qwen/Gemini/Ollama)")
    onboard.add_argument("--ai-provider", default="", help="AI provider: openai or qwen or gemini or ollama")
    onboard.add_argument("--ai-base-url", default="", help="AI base URL")
    onboard.add_argument("--ai-model", default="", help="AI model name")
    onboard.add_argument("--qgis-process", default="", help="qgis_process path")
    onboard.add_argument("--default-bbox", default="", help="default bbox")
    onboard.add_argument("--registry", default="", help="skills registry path")
    onboard.add_argument("--workspace", default="", help="default workspace path")
    onboard.add_argument("--non-interactive", action="store_true", help="no prompt mode")
    onboard.set_defaults(func=cmd_onboard)

    cfg = sub.add_parser("config", help="config operations")
    cfg_sub = cfg.add_subparsers(dest="config_cmd", required=True)
    cfg_show = cfg_sub.add_parser("show", help="print current config")
    cfg_show.set_defaults(func=cmd_config_show)
    cfg_set = cfg_sub.add_parser("set", help="update AI/model/runtime settings")
    cfg_set.add_argument("--api-key", default="", help="AI API key (optional)")
    cfg_set.add_argument("--ai-provider", default="", help="openai | qwen | gemini | ollama")
    cfg_set.add_argument("--ai-base-url", default="", help="AI base URL")
    cfg_set.add_argument("--ai-model", default="", help="AI model name")
    cfg_set.add_argument("--qgis-process", default="", help="qgis_process path")
    cfg_set.add_argument("--default-bbox", default="", help="default bbox")
    cfg_set.add_argument("--registry", default="", help="skills registry path")
    cfg_set.add_argument("--workspace", default="", help="default workspace path")
    cfg_set.set_defaults(func=cmd_config_set)

    envp = sub.add_parser("env", help="print shell source command")
    envp.set_defaults(func=cmd_env)

    update = sub.add_parser("update", help="self-check updates and optionally pull latest code")
    update.add_argument("--check-only", action="store_true", help="only check if remote has newer commits")
    update.add_argument("--remote", default="origin", help="git remote name")
    update.add_argument("--branch", default="main", help="git branch to track")
    update.add_argument("--rebase", action="store_true", help="use rebase mode when pulling")
    update.add_argument("--force", action="store_true", help="allow pull even when workspace has local changes")
    update.add_argument("--skip-install", action="store_true", help="skip pip editable reinstall after pull")
    update.set_defaults(func=cmd_update)

    profile = sub.add_parser("profile", help="manage soul/user profile layers")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)
    profile_init = profile_sub.add_parser("init", help="initialize default soul.md and user.md")
    profile_init.set_defaults(func=cmd_profile_init)
    profile_show = profile_sub.add_parser("show", help="show loaded profile layers")
    profile_show.add_argument("--reload", action="store_true", help="force reload from files")
    profile_show.set_defaults(func=cmd_profile_show)
    profile_evolve = profile_sub.add_parser(
        "evolve",
        help="append dialogue summary and update user.md/soul.md overrides (non-safety keys)",
    )
    profile_evolve.add_argument(
        "--target",
        default="user",
        choices=["user", "soul", "both"],
        help="target layer to update",
    )
    profile_evolve.add_argument(
        "--allow-soul",
        action="store_true",
        help="required when target includes soul",
    )
    profile_evolve.add_argument("--summary", default="", help="dialogue summary for profile update trace")
    profile_evolve.add_argument(
        "--set",
        dest="set_items",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="set one scalar/list key (repeatable)",
    )
    profile_evolve.add_argument(
        "--add",
        dest="add_items",
        action="append",
        default=[],
        metavar="KEY=VALUE1,VALUE2",
        help="append list values (repeatable)",
    )
    profile_evolve.add_argument("--dry-run", action="store_true", help="preview update without writing files")
    profile_evolve.set_defaults(func=cmd_profile_evolve)

    skill = sub.add_parser("skill", help="proxy to scripts/geoclaw_skill_runner.py")
    skill.add_argument("extra", nargs=argparse.REMAINDER, help="args passed to skill runner")
    skill.set_defaults(func=cmd_skill)

    skill_registry = sub.add_parser("skill-registry", help="assess and register skills with security guard")
    skill_registry_sub = skill_registry.add_subparsers(dest="skill_registry_cmd", required=True)

    skill_assess = skill_registry_sub.add_parser("assess", help="assess risk for one skill spec JSON")
    skill_assess.add_argument("--spec-file", required=True, help="path to one skill JSON object file")
    skill_assess.add_argument("--registry", default="", help="target skills registry path")
    skill_assess.set_defaults(func=cmd_skill_registry_assess)

    skill_register = skill_registry_sub.add_parser("register", help="register skill after assessment and confirmation")
    skill_register.add_argument("--spec-file", required=True, help="path to one skill JSON object file")
    skill_register.add_argument("--registry", default="", help="target skills registry path")
    skill_register.add_argument("--replace", action="store_true", help="replace existing skill id if exists")
    skill_register.add_argument("--allow-high-risk", action="store_true", help="allow high-risk skill registration")
    skill_register.add_argument("--confirm", action="store_true", help="confirm registration without interactive prompt")
    skill_register.set_defaults(func=cmd_skill_registry_register)

    skill_import_openclaw = skill_registry_sub.add_parser(
        "import-openclaw",
        help="import OpenClaw-style skill spec (JSON/YAML), assess, then register",
    )
    skill_import_openclaw.add_argument("--spec-file", required=True, help="OpenClaw skill spec JSON/YAML file")
    skill_import_openclaw.add_argument("--registry", default="", help="target skills registry path")
    skill_import_openclaw.add_argument("--id-prefix", default="openclaw_", help="prefix for imported skill id")
    skill_import_openclaw.add_argument("--replace", action="store_true", help="replace existing skill id if exists")
    skill_import_openclaw.add_argument(
        "--allow-high-risk",
        action="store_true",
        help="allow high-risk skill registration",
    )
    skill_import_openclaw.add_argument("--confirm", action="store_true", help="confirm registration without prompt")
    skill_import_openclaw.add_argument("--dry-run", action="store_true", help="only convert + assess, do not register")
    skill_import_openclaw.set_defaults(func=cmd_skill_registry_import_openclaw)

    run = sub.add_parser("run", help="run built-in cases with city/bbox/local data")
    run.add_argument(
        "--case",
        default="native_cases",
        choices=["location_analysis", "site_selection", "native_cases", "wuhan_advanced"],
    )
    run_src = run.add_mutually_exclusive_group()
    run_src.add_argument("--city", default="", help="city name for geocoding and OSM download")
    run_src.add_argument("--bbox", default="", help="south,west,north,east")
    run_src.add_argument("--data-dir", default="", help="local data folder with required GeoJSON files")
    run.add_argument("--tag", default="", help="output tag")
    run.add_argument("--raw-dir", default="", help="raw data folder for download/cache")
    run.add_argument(
        "--out-root",
        default="",
        help="analysis outputs root (fixed to data/outputs by security policy)",
    )
    run.add_argument("--top-n", type=int, default=12, help="top candidates in site selection")
    run.add_argument("--timeout", type=int, default=120, help="download timeout")
    run.add_argument("--skip-download", action="store_true")
    run.add_argument("--force-download", action="store_true")
    run.add_argument("--with-maps", action="store_true")
    run.add_argument("--no-maps", action="store_true")
    run.add_argument("--qgis-python", default="", help="qgis python path for map export")
    run.set_defaults(func=cmd_run)

    operator = sub.add_parser("operator", help="run a single QGIS algorithm with flexible params")
    operator.add_argument("--algorithm", required=True, help="algorithm id, e.g. native:buffer")
    operator.add_argument("--qgis-process", default="", help="optional qgis_process path")
    operator.add_argument("--step-id", default="operator_run", help="step id in output payload")
    operator.add_argument("--param", action="append", default=[], help="string param KEY=VALUE")
    operator.add_argument("--param-json", action="append", default=[], help="json param KEY=JSON")
    operator.add_argument("--params-file", default="", help="json/yaml file containing params")
    operator.add_argument("--dry-run", action="store_true", help="print command without execution")
    operator.set_defaults(func=cmd_operator)

    network = sub.add_parser("network", help="complex mobility network analysis via trackintel")
    network.add_argument("--pfs-csv", required=True, help="positionfix csv path")
    network.add_argument(
        "--out-dir",
        default="data/outputs/network_trackintel",
        help="output directory (must be under data/outputs)",
    )
    network.add_argument("--sep", default=",", help="csv separator")
    network.add_argument("--index-col", default="", help="optional index column name")
    network.add_argument("--tz", default="UTC", help="timezone for tracked_at parsing")
    network.add_argument("--crs", default="EPSG:4326", help="coordinate reference system")
    network.add_argument(
        "--columns-map",
        default="",
        help='json mapping for input columns, e.g. {"time":"tracked_at","uid":"user_id"}',
    )
    network.add_argument("--staypoint-dist-threshold", type=float, default=100.0, help="staypoint distance threshold (m)")
    network.add_argument("--staypoint-time-threshold", type=float, default=5.0, help="staypoint time threshold (min)")
    network.add_argument("--gap-threshold", type=float, default=15.0, help="tripleg/trip gap threshold (min)")
    network.add_argument(
        "--activity-time-threshold",
        type=float,
        default=15.0,
        help="staypoint activity threshold for trip generation (min)",
    )
    network.add_argument("--location-epsilon", type=float, default=100.0, help="DBSCAN epsilon for locations (m)")
    network.add_argument("--location-min-samples", type=int, default=2, help="DBSCAN min samples for locations")
    network.add_argument(
        "--location-agg-level",
        default="user",
        choices=["user", "dataset"],
        help="location aggregation level",
    )
    network.add_argument("--dry-run", action="store_true", help="only print resolved parameters")
    network.set_defaults(func=cmd_network)

    local = sub.add_parser("local", help="run any local tool/command")
    local.add_argument("--cmd", required=True, help='command text, e.g. "ls -la"')
    local.add_argument("--cwd", default="", help="optional working directory")
    local.add_argument("--timeout", type=int, default=120, help="command timeout seconds")
    local.add_argument("--shell", action="store_true", help="run command through shell")
    local.set_defaults(func=cmd_local)

    chat = sub.add_parser("chat", help="chat mode (AI-first; requires configured AI provider)")
    chat.add_argument("message", nargs="*", help="chat message text")
    chat.add_argument("--message", dest="message_opt", default="", help="chat message text (option form)")
    chat.add_argument("--with-ai", action="store_true", help="AI response is enabled by default; this flag is optional")
    chat.add_argument("--no-ai", action="store_true", help=argparse.SUPPRESS)
    chat.add_argument("--interactive", action="store_true", help="start continuous multi-turn chat mode")
    chat.add_argument("--session-id", default="", help="reuse one chat session id for context continuity")
    chat.add_argument("--new-session", action="store_true", help="start a new session (optionally with --session-id)")
    chat.add_argument("--max-history-turns", type=int, default=8, help="max recent turns used as chat context")
    chat.add_argument("--execute", action="store_true", help="execute parsed workflow when message is actionable")
    chat.add_argument("--use-sre", action="store_true", help="enable SRE when executing actionable workflow")
    chat.add_argument("--sre-report-out", default="", help="optional SRE report output path used with --execute")
    chat.set_defaults(func=cmd_chat)

    reasoning = sub.add_parser("reasoning", help="run Spatial Reasoning Engine (internal)")
    reasoning.add_argument("query", nargs="+", help="reasoning query text")
    reasoning.add_argument("--datasets-file", default="", help="JSON datasets payload file")
    reasoning.add_argument("--data-dir", default="", help="auto-discover datasets from local directory")
    reasoning.add_argument("--planner-task", default="", help="planner candidate task type")
    reasoning.add_argument("--planner-method", action="append", default=[], help="planner candidate method (repeatable)")
    reasoning.add_argument("--project-study-area", default="", help="project study area")
    reasoning.add_argument("--project-crs", default="", help="project default CRS")
    reasoning.add_argument("--project-goal", default="", help="project analysis goal")
    reasoning.add_argument(
        "--reasoner-mode",
        default="",
        choices=["", "auto", "deterministic", "external"],
        help="optional override for SRE reasoner mode",
    )
    reasoning.add_argument("--llm-retries", type=int, default=0, help="optional override for external LLM retries")
    reasoning.add_argument("--strict-external", action="store_true", help="fail if external reasoner is unavailable")
    reasoning.add_argument(
        "--report-out",
        default="",
        help="optional markdown report output path (must be under data/outputs)",
    )
    reasoning.add_argument("--print-report", action="store_true", help="print markdown report after JSON payload")
    reasoning.add_argument("--strict", action="store_true", help="return non-zero if validation fails")
    reasoning.set_defaults(func=cmd_reasoning)

    memory = sub.add_parser("memory", help="manage short-term and long-term task memory")
    memory_sub = memory.add_subparsers(dest="memory_cmd", required=True)

    mem_status = memory_sub.add_parser("status", help="show memory storage status")
    mem_status.add_argument("--limit", type=int, default=20, help="reserved for future status sampling")
    mem_status.set_defaults(func=cmd_memory_status)

    mem_short = memory_sub.add_parser("short", help="list short-term task memory")
    mem_short.add_argument("--limit", type=int, default=20, help="max number of short-term tasks")
    mem_short.add_argument("--status", default="", choices=["", "running", "success", "failed"], help="optional status filter")
    mem_short.set_defaults(func=cmd_memory_short)

    mem_long = memory_sub.add_parser("long", help="list long-term reviewed memory")
    mem_long.add_argument("--limit", type=int, default=20, help="max number of long-term entries")
    mem_long.set_defaults(func=cmd_memory_long)

    mem_review = memory_sub.add_parser("review", help="manually review one short-term task into long-term memory")
    mem_review.add_argument("--task-id", required=True, help="short-term task id")
    mem_review.add_argument("--summary", default="", help="custom review summary")
    mem_review.add_argument("--lesson", action="append", default=[], help="repeatable lesson item")
    mem_review.add_argument("--action", action="append", default=[], help="repeatable next action item")
    mem_review.set_defaults(func=cmd_memory_review)

    mem_archive = memory_sub.add_parser("archive", help="archive short-term memory entries")
    mem_archive.add_argument("--before-days", type=int, default=7, help="archive tasks older than N days")
    mem_archive.add_argument("--status", default="", choices=["", "running", "success", "failed"], help="optional status filter")
    mem_archive.add_argument("--include-running", action="store_true", help="allow archiving running tasks")
    mem_archive.set_defaults(func=cmd_memory_archive)

    mem_search = memory_sub.add_parser("search", help="vector retrieval over task memories")
    mem_search.add_argument("--query", required=True, help="query text")
    mem_search.add_argument("--scope", default="long", choices=["short", "long", "archive", "all"], help="memory scope")
    mem_search.add_argument("--top-k", type=int, default=5, help="top-k results")
    mem_search.add_argument("--min-score", type=float, default=0.15, help="minimum similarity score")
    mem_search.set_defaults(func=cmd_memory_search)

    nl = sub.add_parser("nl", help="run geoclaw-openai from natural language (run/operator/network/skill/memory/update/profile/chat/local)")
    nl.add_argument("query", nargs="+", help="natural language request text")
    nl.add_argument("--use-sre", action="store_true", help="use SRE for gray-route planning")
    nl.add_argument("--sre-strict", action="store_true", help="fail when SRE validation status is fail")
    nl.add_argument("--sre-data-dir", default="", help="optional data dir for SRE dataset discovery")
    nl.add_argument("--sre-datasets-file", default="", help="optional JSON file for SRE datasets")
    nl.add_argument(
        "--sre-reasoner-mode",
        default="",
        choices=["", "auto", "deterministic", "external"],
        help="optional override for SRE reasoner mode",
    )
    nl.add_argument("--sre-llm-retries", type=int, default=0, help="optional override for external LLM retries")
    nl.add_argument("--sre-strict-external", action="store_true", help="fail if external reasoner is unavailable")
    nl.add_argument(
        "--sre-report-out",
        default="",
        help="optional markdown report output path from SRE result (must be under data/outputs)",
    )
    nl.add_argument("--sre-print-report", action="store_true", help="print SRE markdown report after JSON payload")
    nl.add_argument("--execute", action="store_true", help="execute parsed command immediately")
    nl.set_defaults(func=cmd_nl)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    bootstrap_runtime_env()
    try:
        get_session_profile()
    except Exception as exc:
        print(f"[PROFILE][WARN] failed to load soul/user profile layers: {exc}", file=sys.stderr)

    if getattr(args, "command", "") == "memory":
        return int(args.func(args))

    store = TaskMemoryStore(session_profile=get_session_profile())
    task_id = store.start_task(
        command=str(getattr(args, "command", "unknown")),
        argv=raw_argv,
        cwd=str(Path.cwd().resolve()),
    )

    rc = 1
    error = ""
    try:
        rc = int(args.func(args))
        return rc
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        try:
            store.finish_task(task_id, rc, error=error)
            store.auto_review_to_long(task_id)
            print(f"[MEMORY] task_id={task_id}")
        except Exception as mem_exc:  # pragma: no cover - memory must not break business command.
            print(f"[MEMORY][WARN] {mem_exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
