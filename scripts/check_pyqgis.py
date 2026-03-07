#!/usr/bin/env python3
"""PyQGIS availability check."""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path


def detect_prefix_path() -> str | None:
    env_prefix = os.environ.get("QGIS_PREFIX_PATH")
    if env_prefix and Path(env_prefix).exists():
        return env_prefix

    candidates = [
        "/Applications/QGIS.app/Contents/MacOS",
        "/Applications/QGIS-LTR.app/Contents/MacOS",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def plugin_paths(prefix_path: str | None) -> list[str]:
    paths: list[str] = []
    if prefix_path:
        root = Path(prefix_path).resolve().parent
        p = root / "Resources" / "python" / "plugins"
        if p.exists():
            paths.append(str(p))

    defaults = [
        "/Applications/QGIS.app/Contents/Resources/python/plugins",
        "/Applications/QGIS-LTR.app/Contents/Resources/python/plugins",
    ]
    for item in defaults:
        if Path(item).exists() and item not in paths:
            paths.append(item)
    return paths


def main() -> int:
    prefix = detect_prefix_path()
    result = {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "qgis_prefix_path_env": os.environ.get("QGIS_PREFIX_PATH", ""),
        "detected_qgis_prefix_path": prefix,
        "pyqgis_import": False,
        "qgis_version": None,
        "processing_available": False,
        "processing_error": None,
        "error": None,
    }

    try:
        from qgis.core import Qgis, QgsApplication  # type: ignore

        result["pyqgis_import"] = True
        if prefix:
            QgsApplication.setPrefixPath(prefix, True)
        qgs = QgsApplication([], False)
        qgs.initQgis()
        try:
            if hasattr(QgsApplication, "qgisVersion"):
                result["qgis_version"] = QgsApplication.qgisVersion()
            else:
                result["qgis_version"] = Qgis.QGIS_VERSION

            for p in plugin_paths(prefix):
                if p not in sys.path:
                    sys.path.append(p)
            try:
                import processing  # type: ignore

                result["processing_available"] = True
            except Exception as exc:
                result["processing_available"] = False
                result["processing_error"] = f"{type(exc).__name__}: {exc}"
        finally:
            qgs.exitQgis()
    except Exception as exc:  # pragma: no cover
        result["error"] = f"{type(exc).__name__}: {exc}"

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pyqgis_import"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
