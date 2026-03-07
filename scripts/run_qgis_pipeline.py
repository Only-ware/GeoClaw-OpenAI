#!/usr/bin/env python3
"""Run a QGIS processing pipeline from YAML configuration."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geoclaw_qgis.config import bootstrap_runtime_env
from geoclaw_qgis.project_info import PROJECT_ATTRIBUTION, PROJECT_VERSION
from geoclaw_qgis.security import OutputSecurityError, validate_output_targets

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run QGIS pipeline from YAML")
    parser.add_argument(
        "--config",
        default="pipelines/wuhan_geoclaw.yaml",
        help="pipeline yaml path",
    )
    parser.add_argument(
        "--qgis-process",
        default="",
        help="optional explicit qgis_process binary path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only print resolved commands",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override pipeline variables (repeatable)",
    )
    parser.add_argument(
        "--set-json",
        action="append",
        default=[],
        metavar="KEY=JSON",
        help="override pipeline variables with JSON typed value (repeatable)",
    )
    parser.add_argument(
        "--vars-file",
        default="",
        help="JSON/YAML file containing variable overrides",
    )
    return parser.parse_args()


def pick_qgis_process(explicit: str = "") -> str:
    if explicit:
        p = Path(explicit)
        if p.exists() and p.is_file():
            return str(p)
        raise FileNotFoundError(f"qgis_process not found at {explicit}")

    env_qp = os.environ.get("GEOCLAW_OPENAI_QGIS_PROCESS", "").strip()
    if env_qp:
        p = Path(env_qp)
        if p.exists() and p.is_file():
            return str(p)

    candidates = [
        "qgis_process",
        "/Applications/QGIS.app/Contents/MacOS/bin/qgis_process",
        "/Applications/QGIS-LTR.app/Contents/MacOS/bin/qgis_process",
    ]
    for candidate in candidates:
        if "/" in candidate:
            p = Path(candidate)
            if p.exists() and p.is_file():
                return str(p)
        else:
            from shutil import which

            found = which(candidate)
            if found:
                return found
    raise FileNotFoundError("qgis_process not found in PATH or common macOS paths")


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is not None:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        # TODO: Replace external parser fallback with bundled minimal YAML parser for better portability.
        data = load_yaml_via_external_python(path)
    if not isinstance(data, dict):
        raise ValueError("pipeline yaml root must be a mapping")
    return data


def parse_overrides(raw_items: list[str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for item in raw_items:
        text = str(item).strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"invalid --set value (expect KEY=VALUE): {item}")
        key, value = text.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --set key: {item}")
        overrides[key] = value
    return overrides


def parse_json_overrides(raw_items: list[str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for item in raw_items:
        text = str(item).strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"invalid --set-json value (expect KEY=JSON): {item}")
        key, raw_json = text.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --set-json key: {item}")
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON for --set-json {key}: {exc}") from exc
        overrides[key] = parsed
    return overrides


def load_vars_file(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"vars file not found: {path}")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        parsed = json.loads(text)
    else:
        if yaml is not None:
            parsed = yaml.safe_load(text)
        else:
            parsed = load_yaml_via_external_python(path)
    if not isinstance(parsed, dict):
        raise ValueError(f"vars file must contain a mapping: {path}")
    return parsed


def load_yaml_via_external_python(path: Path) -> dict[str, Any]:
    candidates = [
        "/Applications/QGIS.app/Contents/MacOS/bin/python3",
        "/Applications/QGIS-LTR.app/Contents/MacOS/bin/python3",
    ]
    for py in candidates:
        if not Path(py).exists():
            continue
        cmd = [
            py,
            "-c",
            (
                "import json,sys,yaml; "
                "print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding='utf-8').read())))"
            ),
            str(path),
        ]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode == 0:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, dict):
                return parsed
    raise ModuleNotFoundError(
        "No yaml parser available. Install PyYAML in current python or ensure QGIS bundled python exists."
    )


def to_text(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        # TODO: Support repeated parameter emission for multilayer inputs instead of simple join.
        return ";".join(to_text(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def resolve_text(text: str, context: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key not in context:
            raise KeyError(f"unresolved variable: {key}")
        return to_text(context[key])

    return VAR_PATTERN.sub(repl, text)


def resolve_value(value: Any, context: dict[str, Any]) -> str:
    if isinstance(value, str):
        return resolve_text(value, context)
    return to_text(value)


def cleanup_existing_outputs(step_id: str, output_paths: dict[str, Path]) -> None:
    for key, path in output_paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.is_file():
            path.unlink()
            print(f"[PIPELINE] {step_id}: removed existing output {path} ({key})")


def run_step(qgis_bin: str, step: dict[str, Any], context: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    step_id = step["id"]
    algorithm = step["algorithm"]
    raw_params = step.get("params") or {}
    if not isinstance(raw_params, dict):
        raise ValueError(f"step {step_id} params must be mapping")

    params: dict[str, str] = {}
    for key, value in raw_params.items():
        params[str(key)] = resolve_value(value, context)

    try:
        output_paths = validate_output_targets(params, workspace_root=ROOT)
    except OutputSecurityError as exc:
        raise RuntimeError(f"step {step_id} failed output security check: {exc}") from exc

    if not dry_run:
        cleanup_existing_outputs(str(step_id), output_paths)

    command = [qgis_bin, "--json", "run", algorithm, "--"] + [f"{k}={v}" for k, v in params.items()]
    print(f"[PIPELINE] {step_id}: {algorithm}")

    if dry_run:
        print("  " + " ".join(command))
        simulated_results = {k: v for k, v in params.items() if "OUTPUT" in k.upper()}
        return {"inputs": params, "results": simulated_results}

    proc = subprocess.run(command, check=False, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"step {step_id} failed (code={proc.returncode})\n"
            f"stdout:\n{proc.stdout}\n\n"
            f"stderr:\n{proc.stderr}"
        )

    payload: dict[str, Any]
    try:
        parsed = json.loads(proc.stdout)
        if isinstance(parsed, dict):
            payload = parsed
        else:
            payload = {"raw": parsed}
    except json.JSONDecodeError:
        payload = {"raw": proc.stdout}

    return {
        "inputs": params,
        "results": payload.get("results") if isinstance(payload, dict) else {},
        "raw": payload,
    }


def main() -> int:
    bootstrap_runtime_env()
    args = parse_args()
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")

    cfg = load_yaml(config_path)
    variables = cfg.get("variables") or {}
    if not isinstance(variables, dict):
        raise ValueError("variables must be a mapping")
    file_overrides = load_vars_file(args.vars_file)
    plain_overrides = parse_overrides(args.set)
    json_overrides = parse_json_overrides(args.set_json)
    overrides: dict[str, Any] = {}
    overrides.update(file_overrides)
    overrides.update(plain_overrides)
    overrides.update(json_overrides)
    if overrides:
        variables = {**variables, **overrides}

    steps = cfg.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a non-empty list")

    context: dict[str, Any] = {k: v for k, v in variables.items()}
    # TODO: Add schema-level validation and typed coercion for pipeline config.

    qgis_bin = pick_qgis_process(args.qgis_process)
    print(f"[PIPELINE] config={config_path}")
    print(f"[PIPELINE] qgis_process={qgis_bin}")
    if overrides:
        print(f"[PIPELINE] variable_overrides={json.dumps(overrides, ensure_ascii=False)}")

    out_dir = resolve_value(variables.get("out_dir", "data/outputs"), context)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "pipeline": cfg.get("name", config_path.stem),
        "version": PROJECT_VERSION,
        "attribution": PROJECT_ATTRIBUTION,
        "config": str(config_path),
        "qgis_process": qgis_bin,
        "variables": variables,
        "steps": {},
    }

    for step in steps:
        if not isinstance(step, dict) or "id" not in step or "algorithm" not in step:
            raise ValueError("each step must contain id and algorithm")

        step_id = str(step["id"])
        result = run_step(qgis_bin, step, context, args.dry_run)
        report["steps"][step_id] = result

        outputs = result.get("results") or {}
        if isinstance(outputs, dict):
            for out_key, out_val in outputs.items():
                context[f"{step_id}.{out_key}"] = out_val
            if "OUTPUT" in outputs:
                context[step_id] = outputs["OUTPUT"]

    report_path = Path(out_dir) / "pipeline_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[PIPELINE] report={report_path}")

    last_step = steps[-1]["id"]
    if isinstance(report["steps"].get(last_step, {}).get("results"), dict):
        final_output = report["steps"][last_step]["results"].get("OUTPUT")
        if final_output:
            print(f"[PIPELINE] final_output={final_output}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[PIPELINE][ERROR] {exc}", file=sys.stderr)
        raise
