from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from geoclaw_qgis.analysis import TrackintelIntegrationError, TrackintelNetworkService
from geoclaw_qgis.config import (
    bootstrap_runtime_env,
    detect_qgis_process,
    env_sh_path,
    geoclaw_home,
    read_config,
    write_config,
    write_env,
    write_env_sh,
)
from geoclaw_qgis.memory import TaskMemoryStore
from geoclaw_qgis.nl import NLPlan, parse_nl_query
from geoclaw_qgis.project_info import LAB_AFFILIATION, PROJECT_NAME, PROJECT_VERSION


DEFAULT_BBOX = "30.50,114.20,30.66,114.45"
DEFAULT_AI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AI_MODEL = "gpt-4.1-mini"
DEFAULT_REGISTRY = "configs/skills_registry.json"


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

    api_base_url = args.ai_base_url or defaults.get("ai_base_url", DEFAULT_AI_BASE_URL)
    ai_model = args.ai_model or defaults.get("ai_model", DEFAULT_AI_MODEL)
    default_bbox = args.default_bbox or defaults.get("bbox", DEFAULT_BBOX)
    registry_path = args.registry or defaults.get("registry", DEFAULT_REGISTRY)
    workspace = args.workspace or defaults.get("workspace", str(Path.cwd().resolve()))

    detected_qgis = ""
    try:
        detected_qgis = detect_qgis_process(args.qgis_process or runtime.get("qgis_process", ""))
    except FileNotFoundError:
        detected_qgis = ""

    existing_key = os.environ.get("GEOCLAW_OPENAI_API_KEY", "").strip()

    if not args.non_interactive:
        print(f"GeoClaw-OpenAI home: {geoclaw_home()}")
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

        api_key = args.api_key or ask_secret("OpenAI API Key", default_masked=bool(existing_key))
        if not api_key and existing_key:
            api_key = existing_key
    else:
        api_key = args.api_key or existing_key
        if not detected_qgis:
            detected_qgis = args.qgis_process or runtime.get("qgis_process", "")

    if not api_key:
        raise ValueError("OpenAI API key is required. Use --api-key or run interactive onboard.")

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        "version": "2.0",
        "updated_at": now,
        "defaults": {
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
        "GEOCLAW_OPENAI_BASE_URL": api_base_url,
        "GEOCLAW_OPENAI_API_KEY": api_key,
        "GEOCLAW_OPENAI_MODEL": ai_model,
        "GEOCLAW_OPENAI_DEFAULT_BBOX": default_bbox,
        "GEOCLAW_OPENAI_SKILL_REGISTRY": registry_path,
        "GEOCLAW_OPENAI_WORKSPACE": workspace,
    }
    if detected_qgis:
        env_values["GEOCLAW_OPENAI_QGIS_PROCESS"] = detected_qgis

    config_file = write_config(payload)
    env_file = write_env(env_values)
    env_sh = write_env_sh(env_values)

    print(json.dumps({
        "config": str(config_file),
        "env": str(env_file),
        "env_sh": str(env_sh),
        "qgis_process": detected_qgis,
        "registry": registry_path,
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


def cmd_env(_args: argparse.Namespace) -> int:
    path = env_sh_path()
    if not path.exists():
        print(f"env script not found: {path}")
        return 1
    print(f"source {path}")
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
    store = TaskMemoryStore()
    payload = {
        "memory_root": str(store.short_dir.parent),
        "short_count": store.count_short(),
        "long_count": store.count_long(),
        "short_dir": str(store.short_dir),
        "long_file": str(store.long_file),
        "limit": args.limit,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_short(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    store = TaskMemoryStore()
    rows = store.list_short(limit=args.limit, status=args.status)
    print(json.dumps({"items": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_long(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    store = TaskMemoryStore()
    rows = store.list_long(limit=args.limit)
    print(json.dumps({"items": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def cmd_memory_review(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    store = TaskMemoryStore()
    payload = store.review_task_to_long(
        args.task_id,
        summary=args.summary or "",
        lessons=args.lesson or [],
        next_actions=args.action or [],
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_nl(args: argparse.Namespace) -> int:
    bootstrap_runtime_env()
    query_text = " ".join(args.query).strip()
    if not query_text:
        raise ValueError("query text is required")

    plan: NLPlan = parse_nl_query(query_text)
    payload = {
        "query": plan.query,
        "intent": plan.intent,
        "confidence": plan.confidence,
        "reasons": plan.reasons,
        "command_preview": "geoclaw-openai " + " ".join(plan.cli_args),
        "cli_args": plan.cli_args,
        "execute": bool(args.execute),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not args.execute:
        print("[NL] 预览模式：加 --execute 将执行上述命令。")
        return 0

    current_cli = Path(sys.argv[0]).expanduser()
    if current_cli.exists() and current_cli.is_file() and "geoclaw-openai" in current_cli.name:
        cmd = [str(current_cli), *plan.cli_args]
    else:
        cmd = [os.environ.get("PYTHON", "python3"), "-m", "geoclaw_qgis.cli.main", *plan.cli_args]
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
    onboard.add_argument("--api-key", default="", help="OpenAI API key")
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

    skill = sub.add_parser("skill", help="proxy to scripts/geoclaw_skill_runner.py")
    skill.add_argument("extra", nargs=argparse.REMAINDER, help="args passed to skill runner")
    skill.set_defaults(func=cmd_skill)

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
    run.add_argument("--out-root", default="data/outputs", help="analysis outputs root")
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
    network.add_argument("--out-dir", default="data/outputs/network_trackintel", help="output directory")
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

    nl = sub.add_parser("nl", help="run geoclaw-openai from natural language")
    nl.add_argument("query", nargs="+", help="natural language request text")
    nl.add_argument("--execute", action="store_true", help="execute parsed command immediately")
    nl.set_defaults(func=cmd_nl)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    raw_argv = list(argv) if argv is not None else sys.argv[1:]

    if getattr(args, "command", "") == "memory":
        return int(args.func(args))

    store = TaskMemoryStore()
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
