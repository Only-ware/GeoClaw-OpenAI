#!/usr/bin/env python3
"""Run one QGIS processing algorithm with flexible parameter definitions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geoclaw_qgis.config import bootstrap_runtime_env, detect_qgis_process
from geoclaw_qgis.project_info import LAB_AFFILIATION, PROJECT_ATTRIBUTION, PROJECT_VERSION
from geoclaw_qgis.providers import QgisProcessRunner
from geoclaw_qgis.security import OutputSecurityError, validate_output_targets

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a single qgis_process algorithm with flexible params.")
    p.add_argument("--algorithm", required=True, help="algorithm id, e.g. native:buffer")
    p.add_argument("--qgis-process", default="", help="optional qgis_process path")
    p.add_argument("--step-id", default="operator_run", help="step id for result payload")
    p.add_argument("--param", action="append", default=[], metavar="KEY=VALUE", help="string params")
    p.add_argument("--param-json", action="append", default=[], metavar="KEY=JSON", help="JSON typed params")
    p.add_argument("--params-file", default="", help="JSON/YAML param file")
    p.add_argument("--no-overwrite", action="store_true", help="do not delete existing output targets")
    p.add_argument("--dry-run", action="store_true", help="print generated command only")
    return p.parse_args()


def parse_kv(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"invalid --param value (expect KEY=VALUE): {item}")
        key, value = text.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --param key: {item}")
        out[key] = value
    return out


def parse_kv_json(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"invalid --param-json value (expect KEY=JSON): {item}")
        key, raw_json = text.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --param-json key: {item}")
        out[key] = json.loads(raw_json)
    return out


def load_params_file(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"params file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        parsed = json.loads(text)
    else:
        if yaml is not None:
            parsed = yaml.safe_load(text)
        else:
            qgis_python = Path(detect_qgis_process()).parent / "python3"
            if not qgis_python.exists():
                raise ModuleNotFoundError("PyYAML unavailable and QGIS python fallback not found")
            cmd = [
                str(qgis_python),
                "-c",
                "import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding='utf-8').read())))",
                str(path),
            ]
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
            parsed = json.loads(proc.stdout)
    if not isinstance(parsed, dict):
        raise ValueError(f"params file must contain a mapping: {path}")
    return parsed


def prepare_output_targets(params: dict[str, Any], overwrite: bool) -> None:
    output_paths = validate_output_targets(params, workspace_root=ROOT)
    for path in output_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        if overwrite and path.exists() and path.is_file():
            path.unlink()


def main() -> int:
    bootstrap_runtime_env()
    args = parse_args()

    file_params = load_params_file(args.params_file)
    text_params = parse_kv(args.param)
    json_params = parse_kv_json(args.param_json)

    params: dict[str, Any] = {}
    params.update(file_params)
    params.update(text_params)
    params.update(json_params)

    qgis_process = detect_qgis_process(args.qgis_process)
    if not qgis_process:
        raise FileNotFoundError("qgis_process not found; set --qgis-process or GEOCLAW_OPENAI_QGIS_PROCESS")

    runner = QgisProcessRunner(command=qgis_process)
    try:
        prepare_output_targets(params, overwrite=not args.no_overwrite)
    except OutputSecurityError as exc:
        raise RuntimeError(f"output security check failed: {exc}") from exc
    encoded = [f"{k}={runner.encode_value(v)}" for k, v in params.items()]
    dry_cmd = [qgis_process, "--json", "run", args.algorithm, "--"] + encoded
    if args.dry_run:
        print(json.dumps({"command": dry_cmd, "algorithm": args.algorithm, "params": params}, ensure_ascii=False, indent=2))
        return 0

    result = runner.run_algorithm(args.algorithm, params=params, step_id=args.step_id)
    payload = {
        "version": PROJECT_VERSION,
        "attribution": PROJECT_ATTRIBUTION,
        "lab_affiliation": LAB_AFFILIATION,
        "success": result.success,
        "step_id": result.step_id,
        "algorithm": args.algorithm,
        "params": params,
        "outputs": result.outputs,
        "message": result.message,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
