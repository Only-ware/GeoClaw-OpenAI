from __future__ import annotations

import subprocess
from pathlib import Path


def default_pipeline_path(root: str | Path = ".") -> Path:
    return Path(root) / "pipelines" / "cases" / "site_selection.yaml"


def run_site_selection(pipeline_path: str | Path, python_executable: str = "python3") -> None:
    cmd = [python_executable, "scripts/run_qgis_pipeline.py", "--config", str(pipeline_path)]
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"site selection failed: {' '.join(cmd)}")

    # TODO: Add optional auto-export to candidate map layouts.
