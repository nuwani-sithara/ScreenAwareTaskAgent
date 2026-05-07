"""Configuration for the OpenAI-backed vision pipeline."""

from __future__ import annotations

import os
from pathlib import Path

try:
    _ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
    if _ENV_PATH.exists():
        for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _value = _line.split("=", 1)
            _key = _key.strip()
            _value = _value.strip().strip('"').strip("'")
            if _key:
                os.environ[_key] = _value
except Exception:
    pass

MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4.1")
CONFIDENCE_THRESHOLD = 0.65

# OpenAI API key from environment.
# Support both OPEN_API_KEY (requested) and OPENAI_API_KEY (standard alias).
OPENAI_API_KEY = os.getenv("OPEN_API_KEY") or os.getenv("OPENAI_API_KEY")

# Backward-compatible Gemini aliases so older modules can still import cleanly
# while the active pipeline uses OpenAI by default.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Timeout (seconds) for vision RPCs. Can be overridden in vision/.env
try:
	OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "180"))
except Exception:
	OPENAI_TIMEOUT_SECONDS = 180.0

try:
	GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", str(OPENAI_TIMEOUT_SECONDS)))
except Exception:
	GEMINI_TIMEOUT_SECONDS = OPENAI_TIMEOUT_SECONDS

# Whether to attempt automatic screen boundary detection and crop dark borders.
# Set to "0" in environment to disable cropping and always use full-frame images.
DETECT_SCREEN_BOUNDARIES = os.getenv("VISION_DETECT_BOUNDARIES", "0") != "0"
