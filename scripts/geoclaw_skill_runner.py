#!/usr/bin/env python3
"""Run GeoClaw skills from registry with optional external AI integration."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geoclaw_qgis.ai import ExternalAIClient, ExternalAIConfig, compress_context
from geoclaw_qgis.config import bootstrap_runtime_env
from geoclaw_qgis.profile import load_session_profile
from geoclaw_qgis.skills import SkillRegistry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GeoClaw skill runner")
    parser.add_argument("--registry", default=os.environ.get("GEOCLAW_OPENAI_SKILL_REGISTRY", "configs/skills_registry.json"))
    parser.add_argument("--list", action="store_true", help="list available skills")
    parser.add_argument("--skill", default="", help="skill id to run")
    parser.add_argument("--city", default="", help="city name for OSM download when required")
    parser.add_argument("--bbox", default=os.environ.get("GEOCLAW_OPENAI_DEFAULT_BBOX", ""), help="bbox for OSM download")
    parser.add_argument("--skip-download", action="store_true", help="skip OSM download")
    parser.add_argument(
        "--with-ai",
        dest="with_ai",
        action="store_true",
        help="enable AI summarization (default)",
    )
    parser.add_argument(
        "--no-ai",
        dest="with_ai",
        action="store_false",
        help="disable AI summarization for this run",
    )
    parser.set_defaults(with_ai=True)
    parser.add_argument("--require-ai", action="store_true", help="fail if AI call is unavailable")
    parser.add_argument("--ai-input", default="", help="extra AI prompt text")
    parser.add_argument("--ai-input-file", default="", help="load extra AI prompt text from file")
    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        metavar="TOKEN",
        help="extra token passed to builtin skill command (repeatable)",
    )
    parser.add_argument("--args", default="", help="extra command tokens for builtin skills (shell-style string)")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override pipeline variables for pipeline skills (repeatable)",
    )
    return parser.parse_args()


def run_cmd(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def read_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def run_pipeline_skill(
    skill_id: str,
    registry: SkillRegistry,
    city: str,
    bbox: str,
    skip_download: bool,
    var_overrides: list[str] | None = None,
) -> dict[str, Any]:
    spec = registry.get(skill_id)
    if spec.skill_type != "pipeline":
        raise ValueError(f"skill {skill_id} is not pipeline type")
    var_overrides = list(var_overrides or [])

    for pre in spec.pre_steps:
        pre_spec = registry.get(pre)
        if pre_spec.skill_type == "pipeline":
            run_pipeline_skill(pre, registry, city, bbox, skip_download, var_overrides=var_overrides)

    if spec.requires_osm and not skip_download:
        use_bbox = bbox or spec.default_bbox
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "download_osm_wuhan.py"),
            "--timeout",
            "120",
        ]
        use_city = city.strip()
        if use_city:
            cmd.extend(["--city", use_city])
        else:
            cmd.extend(["--bbox", use_bbox])
        run_cmd(cmd)

    pipeline_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_qgis_pipeline.py"),
        "--config",
        str(ROOT / spec.pipeline),
    ]
    override_map: dict[str, str] = {}
    for item in var_overrides:
        text = str(item).strip()
        if text:
            if "=" in text:
                k, v = text.split("=", 1)
                override_map[k.strip()] = v.strip()
            pipeline_cmd.extend(["--set", text])
    run_cmd(pipeline_cmd)

    report_path = spec.report_path
    out_dir = override_map.get("out_dir", "").strip()
    if out_dir:
        report_path = str(Path(out_dir) / "pipeline_report.json")

    return {
        "skill": spec.skill_id,
        "type": spec.skill_type,
        "pipeline": spec.pipeline,
        "report": report_path,
    }


def _collect_user_tokens(args: argparse.Namespace) -> list[str]:
    tokens: list[str] = []
    for item in args.arg:
        text = str(item).strip()
        if text:
            tokens.append(text)
    if args.args.strip():
        tokens.extend(shlex.split(args.args.strip()))
    return tokens


def run_builtin_skill(
    skill_id: str,
    registry: SkillRegistry,
    *,
    user_tokens: list[str],
) -> dict[str, Any]:
    spec = registry.get(skill_id)
    if spec.skill_type != "builtin":
        raise ValueError(f"skill {skill_id} is not builtin type")
    if not spec.builtin:
        raise ValueError(f"builtin skill {skill_id} missing builtin command")

    root = spec.builtin[0]
    if root not in {"run", "operator", "network", "reasoning"}:
        raise ValueError(f"unsupported builtin root command: {root}")

    cmd = [sys.executable, "-m", "geoclaw_qgis.cli.main", *spec.builtin]
    cmd.extend(list(spec.default_args))
    cmd.extend(user_tokens)
    run_cmd(cmd)
    return {
        "skill": spec.skill_id,
        "type": spec.skill_type,
        "builtin": spec.builtin,
        "default_args": spec.default_args,
        "executed_command": cmd,
    }


def run_ai_skill(skill_id: str, registry: SkillRegistry, ai_text: str, require_ai: bool) -> dict[str, Any]:
    spec = registry.get(skill_id)
    if spec.skill_type != "ai":
        raise ValueError(f"skill {skill_id} is not ai type")

    session = load_session_profile(ROOT)
    routed_system_prompt = (
        f"{spec.system_prompt}\n\n"
        "[Profile Guidance]\n"
        f"- User role: {session.user.role}\n"
        f"- Preferred language: {session.user.preferred_language}\n"
        f"- Preferred tone: {session.user.preferred_tone}\n"
        f"- Soul mission: {session.soul.mission}\n"
    )

    try:
        client = ExternalAIClient(ExternalAIConfig.from_env())
        reply = client.chat(ai_text, system_prompt=routed_system_prompt)
        return {
            "skill": spec.skill_id,
            "type": spec.skill_type,
            "ai_response": reply,
        }
    except Exception as exc:
        if require_ai:
            raise
        return {
            "skill": spec.skill_id,
            "type": spec.skill_type,
            "warning": f"AI call skipped: {exc}",
            "ai_response": "",
        }


def summarize_with_ai(
    skill_id: str,
    registry: SkillRegistry,
    extra_prompt: str,
    require_ai: bool,
    *,
    report_path: str = "",
) -> dict[str, Any]:
    spec = registry.get(skill_id)
    chosen_report = report_path.strip() or spec.report_path
    if chosen_report and not os.path.isabs(chosen_report):
        chosen_report = str(ROOT / chosen_report)
    report_text = read_text(chosen_report) if chosen_report else ""
    compressed_report = compress_context(report_text, max_chars=12000)
    prompt = (
        "请基于以下 GeoClaw pipeline 报告，输出空间分析结论、风险、建议行动。\n"
        "输出结构：1) 结论 2) 风险 3) 选址建议 4) 数据质量建议\n\n"
        f"[skill]={skill_id}\n"
        f"[report]\n{compressed_report.text}\n\n"
        f"[extra]\n{extra_prompt}"
    )

    try:
        client = ExternalAIClient(ExternalAIConfig.from_env())
        reply = client.chat(prompt, system_prompt="You are a GIS site-selection analyst.")
        return {"summary": reply, "report_source": chosen_report}
    except Exception as exc:
        if require_ai:
            raise
        return {"summary": "", "warning": f"AI summary skipped: {exc}", "report_source": chosen_report}


def main() -> int:
    bootstrap_runtime_env()
    args = parse_args()
    session = load_session_profile(ROOT)
    registry = SkillRegistry(ROOT / args.registry)

    if args.list:
        skills = registry.list()
        for item in skills:
            print(f"{item.skill_id}\t{item.skill_type}\t{item.description}")
        return 0

    if not args.skill:
        raise ValueError("--skill is required unless --list is used")

    spec = registry.get(args.skill)
    result: dict[str, Any]
    user_tokens = _collect_user_tokens(args)

    if spec.skill_type == "pipeline":
        result = run_pipeline_skill(
            args.skill,
            registry,
            args.city,
            args.bbox,
            args.skip_download,
            var_overrides=args.set,
        )
    elif spec.skill_type == "ai":
        extra = args.ai_input or read_text(args.ai_input_file)
        result = run_ai_skill(args.skill, registry, extra, args.require_ai)
    elif spec.skill_type == "builtin":
        result = run_builtin_skill(
            args.skill,
            registry,
            user_tokens=user_tokens,
        )
    else:
        raise ValueError(f"unsupported skill type: {spec.skill_type}")

    if args.with_ai and spec.skill_type == "pipeline":
        extra = args.ai_input or read_text(args.ai_input_file)
        report_path = str(result.get("report", "")).strip()
        result["ai"] = summarize_with_ai(
            args.skill,
            registry,
            extra,
            args.require_ai,
            report_path=report_path,
        )

    result["tool_router_context"] = session.tool_router_context()
    result["profile_layers"] = {"soul_path": session.soul_path, "user_path": session.user_path}

    # TODO: Support command/plugin type skills with sandboxed hook execution.
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
