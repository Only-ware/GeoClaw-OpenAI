from __future__ import annotations

def main(argv: list[str] | None = None) -> int:
    # Avoid importing geoclaw_qgis.cli.main at package import time to prevent
    # runpy warnings for `python -m geoclaw_qgis.cli.main`.
    from .main import main as _main

    return int(_main(argv))


__all__ = ["main"]
