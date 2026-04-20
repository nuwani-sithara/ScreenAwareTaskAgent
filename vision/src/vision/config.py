"""Configuration for Gemini-backed vision pipeline."""

from __future__ import annotations

import os

MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-flash-latest")
CONFIDENCE_THRESHOLD = 0.65

# GEMINI API key from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Timeout (seconds) for Gemini RPCs. Can be overridden in vision/.env
try:
	GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "45"))
except Exception:
	GEMINI_TIMEOUT_SECONDS = 45.0

# Whether to attempt automatic screen boundary detection and crop dark borders.
# Set to "0" in environment to disable cropping and always use full-frame images.
DETECT_SCREEN_BOUNDARIES = os.getenv("VISION_DETECT_BOUNDARIES", "0") != "0"
