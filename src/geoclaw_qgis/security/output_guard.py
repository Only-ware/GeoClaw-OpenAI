from __future__ import annotations

from pathlib import Path
from typing import Any


class OutputSecurityError(RuntimeError):
    """Raised when an output path violates fixed output-root security policy."""


SAFE_OUTPUT_ROOT_REL = Path("data/outputs")


def _extract_path_candidate(raw: str) -> str:
    value = raw.strip()
    if "|" in value and not value.startswith("http"):
        value = value.split("|", 1)[0].strip()
    return value


def _is_special_output(value: str) -> bool:
    normalized = value.strip()
    lowered = normalized.lower()
    if not normalized:
        return True
    if normalized == "TEMPORARY_OUTPUT":
        return True
    if lowered.startswith("memory:") or lowered.startswith("/vsimem/"):
        return True
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return True
    if lowered.startswith("dbname=") or lowered.startswith("postgres://"):
        return True
    return False


def _looks_like_path(value: str) -> bool:
    lowered = value.lower()
    if "/" in value or "\\" in value:
        return True
    suffixes = (
        ".gpkg",
        ".geojson",
        ".json",
        ".sqlite",
        ".db",
        ".shp",
        ".tif",
        ".tiff",
        ".vrt",
        ".csv",
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
        ".qgz",
    )
    return lowered.endswith(suffixes)


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_workspace_path(path_text: str, workspace_root: Path) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = (workspace_root / path).resolve()
    else:
        path = path.resolve()
    return path


def validate_output_targets(
    params: dict[str, Any],
    *,
    workspace_root: Path,
    safe_output_root: Path | None = None,
) -> dict[str, Path]:
    safe_root = (safe_output_root or (workspace_root / SAFE_OUTPUT_ROOT_REL)).resolve()

    input_paths: set[Path] = set()
    for key, value in params.items():
        if "OUTPUT" in str(key).upper():
            continue
        if not isinstance(value, str):
            continue
        text = _extract_path_candidate(value)
        if _is_special_output(text) or not _looks_like_path(text):
            continue
        input_paths.add(resolve_workspace_path(text, workspace_root))

    output_paths: dict[str, Path] = {}
    for key, value in params.items():
        k = str(key)
        if "OUTPUT" not in k.upper():
            continue
        if not isinstance(value, str):
            continue

        text = _extract_path_candidate(value)
        if _is_special_output(text) or not _looks_like_path(text):
            continue

        out_path = resolve_workspace_path(text, workspace_root)
        if not _path_is_within(out_path, safe_root):
            raise OutputSecurityError(
                f"Unsafe output path: {out_path}. "
                f"All outputs must be under fixed folder: {safe_root}"
            )
        if out_path in input_paths:
            raise OutputSecurityError(
                f"In-place output detected for '{k}': {out_path}. "
                "Direct overwrite/delete of input files is blocked by security policy."
            )
        output_paths[k] = out_path
    return output_paths


def fixed_output_root(workspace_root: Path) -> Path:
    return (workspace_root / SAFE_OUTPUT_ROOT_REL).resolve()
