"""Repository-level namespace package shim.

This lets commands launched from the repo root import `src.*` modules from
`vision/src` without changing the documented uvicorn command.
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

ROOT = Path(__file__).resolve().parent.parent
VISION_SRC = ROOT / "vision" / "src"
if VISION_SRC.exists():
    vision_src_str = str(VISION_SRC)
    if vision_src_str not in __path__:
        __path__.append(vision_src_str)
