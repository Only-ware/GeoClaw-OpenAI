#!/usr/bin/env python3
"""Run GeoClaw skills from registry with optional external AI integration."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geoclaw_qgis.ai import ExternalAIClient, ExternalAIConfig
from geoclaw_qgis.config import bootstrap_runtime_env
from geoclaw_qgis.skills import SkillRegistry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GeoClaw skill runner")
    parser.add_argument("--registry", default=os.environ.get("GEOCLAW_OPENAI_SKILL_REGISTRY", "configs/skills_registry.json"))
    parser.add_argument("--list", action="store_true", help="list available skills")
    parser.add_argument("--skill", default="", help="skill id to run")
    parser.add_argument("--bbox", default=os.environ.get("GEOCLAW_OPENAI_DEFAULT_BBOX", ""), help="bbox for OSM download")
    parser.add_argument("--skip-download", action="store_true", help="skip OSM download")
    parser.add_argument("--with-ai", action="store_true", help="run external AI summarization")
    parser.add_argument("--require-ai", action="store_true", help="fail if AI call is unavailable")
    parser.add_argument("--ai-input", default="", help="extra AI prompt text")
    parser.add_argument("--ai-input-file", default="", help="load extra AI prompt text from file")
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


def run_pipeline_skill(skill_id: str, registry: SkillRegistry, bbox: str, skip_download: bool) -> dict[str, Any]:
    spec = registry.get(skill_id)
    if spec.skill_type != "pipeline":
        raise ValueError(f"skill {skill_id} is not pipeline type")

    for pre in spec.pre_steps:
        pre_spec = registry.get(pre)
        if pre_spec.skill_type == "pipeline":
            run_pipeline_skill(pre, registry, bbox, skip_download)

    if spec.requires_osm and not skip_download:
        use_bbox = bbox or spec.default_bbox
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "download_osm_wuhan.py"),
            "--bbox",
            use_bbox,
            "--timeout",
            "120",
        ]
        run_cmd(cmd)

    pipeline_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_qgis_pipeline.py"),
        "--config",
        str(ROOT / spec.pipeline),
    ]
    run_cmd(pipeline_cmd)

    return {
        "skill": spec.skill_id,
        "type": spec.skill_type,
        "pipeline": spec.pipeline,
        "report": spec.report_path,
    }


def run_ai_skill(skill_id: str, registry: SkillRegistry, ai_text: str, require_ai: bool) -> dict[str, Any]:
    spec = registry.get(skill_id)
    if spec.skill_type != "ai":
        raise ValueError(f"skill {skill_id} is not ai type")

    try:
        client = ExternalAIClient(ExternalAIConfig.from_env())
        reply = client.chat(ai_text, system_prompt=spec.system_prompt)
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


def summarize_with_ai(skill_id: str, registry: SkillRegistry, extra_prompt: str, require_ai: bool) -> dict[str, Any]:
    spec = registry.get(skill_id)
    report_text = read_text(str(ROOT / spec.report_path)) if spec.report_path else ""
    prompt = (
        "请基于以下 GeoClaw pipeline 报告，输出空间分析结论、风险、建议行动。\n"
        "输出结构：1) 结论 2) 风险 3) 选址建议 4) 数据质量建议\n\n"
        f"[skill]={skill_id}\n"
        f"[report]\n{report_text[:12000]}\n\n"
        f"[extra]\n{extra_prompt}"
    )

    try:
        client = ExternalAIClient(ExternalAIConfig.from_env())
        reply = client.chat(prompt, system_prompt="You are a GIS site-selection analyst.")
        return {"summary": reply}
    except Exception as exc:
        if require_ai:
            raise
        return {"summary": "", "warning": f"AI summary skipped: {exc}"}


def main() -> int:
    bootstrap_runtime_env()
    args = parse_args()
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

    if spec.skill_type == "pipeline":
        result = run_pipeline_skill(args.skill, registry, args.bbox, args.skip_download)
    elif spec.skill_type == "ai":
        extra = args.ai_input or read_text(args.ai_input_file)
        result = run_ai_skill(args.skill, registry, extra, args.require_ai)
    else:
        raise ValueError(f"unsupported skill type: {spec.skill_type}")

    if args.with_ai and spec.skill_type == "pipeline":
        extra = args.ai_input or read_text(args.ai_input_file)
        result["ai"] = summarize_with_ai(args.skill, registry, extra, args.require_ai)

    # TODO: Support command/plugin type skills with sandboxed hook execution.
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
