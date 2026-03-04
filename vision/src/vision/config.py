"""Configuration for Gemini-backed vision pipeline."""

from __future__ import annotations

import os

MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-flash-latest")
CONFIDENCE_THRESHOLD = 0.65

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
