from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

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
from geoclaw_qgis.memory import TaskMemoryStore
from geoclaw_qgis.nl import NLPlan, parse_nl_query
from geoclaw_qgis.profile import SessionProfile, ensure_profile_layers, load_session_profile
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
from geoclaw_qgis.skills import assess_skill_spec, load_skill_spec_file, upsert_skill_registry


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
}
_SESSION_PROFILE: SessionProfile | None = None
_PATH_HINT_RE = re.compile(r"([~./A-Za-z0-9_\\-]+/[A-Za-z0-9_./\\-]+)")
_SRE_ALLOWED_ROOT_COMMANDS = {"run", "operator", "network", "skill", "memory", "update", "reasoning"}
_RUN_CASE_CHOICES = {"location_analysis", "site_selection", "native_cases", "wuhan_advanced"}
_SRE_SPATIAL_INTENTS = {"run", "operator", "network", "skill"}
_RUN_SOURCE_FLAGS = ("--data-dir", "--bbox", "--city")
_RUN_BOOL_FLAGS = ("--with-maps", "--no-maps", "--skip-download", "--force-download")
_RUN_VALUE_FLAGS = ("--top-n", "--timeout", "--tag", "--raw-dir", "--out-root")


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


def ask_secret(prompt: str, default_masked: bool = False) -> str:
    suffix = " [已配置, 回车保持]" if default_masked else ""
    return getpass.getpass(f"{prompt}{suffix}: ").strip()


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
    )

    if not args.non_interactive:
        print(f"GeoClaw-OpenAI home: {geoclaw_home()}")
        ai_provider = ask_value("AI Provider (openai/qwen/gemini)", ai_provider).strip().lower() or ai_provider
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

        api_key = args.api_key or ask_secret(f"{ai_provider.upper()} API Key", default_masked=bool(existing_key))
        if not api_key and existing_key:
            api_key = existing_key
    else:
        api_key = args.api_key or existing_key
        if not detected_qgis:
            detected_qgis = args.qgis_process or runtime.get("qgis_process", "")

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
    )
    api_key = str(args.api_key or existing_api_key).strip()

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
    routed_cli_args = list(plan.cli_args)
    route_notes: list[str] = []
    sre_input_data = None
    sre_result = None
    locked_cli_args: list[str] | None = None
    query_lower = query_text.lower()
    if plan.intent in {"run", "operator"} and any(k in query_lower for k in ("mall", "shopping", "商场")):
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
                    "Kept explicit NL-prioritized skill route; rejected conflicting SRE reroute."
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

    if assessment.get("risk_level") == "high" and not args.allow_high_risk:
        _append_skill_guard_log(
            {
                "action": "register_blocked",
                "spec_file": str(spec_path),
                "registry": str(registry_path),
                "assessment": assessment,
                "reason": "high_risk_requires_allow_high_risk",
            }
        )
        raise RuntimeError(
            "Skill assessment risk_level=high. Registration blocked. "
            "Review findings and use --allow-high-risk with explicit confirmation if you still want to proceed."
        )

    confirmed = bool(args.confirm)
    if not confirmed:
        if not sys.stdin.isatty():
            raise ValueError("--confirm is required in non-interactive mode.")
        prompt = "Assessment complete. Type YES to confirm registration: "
        answer = input(prompt).strip()
        confirmed = answer == "YES"
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
    onboard.add_argument("--api-key", default="", help="AI API key (OpenAI/Qwen/Gemini)")
    onboard.add_argument("--ai-provider", default="", help="AI provider: openai or qwen or gemini")
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
    cfg_set.add_argument("--ai-provider", default="", help="openai | qwen | gemini")
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

    nl = sub.add_parser("nl", help="run geoclaw-openai from natural language")
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
