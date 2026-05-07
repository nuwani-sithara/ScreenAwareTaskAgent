"""Shared runtime environment loading for backend modules.

This keeps backend/core modules consistent when they are imported directly
from the app, tests, or scripts. The backend's `.env` file is loaded once
before any module reads `os.getenv(...)` for service routing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_runtime_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    backend_dir = Path(__file__).resolve().parents[1]
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

