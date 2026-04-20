"""Orchestrator for Gemini semantic vision analysis with validation and debug overlay."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import cv2

from src.vision.debug.overlay_generator import generate_overlay
from src.vision.validation.coordinate_validator import validate_coordinates
from src.vision.validation.schema_validator import build_empty_response, validate_schema
from src.vision.vlm.gemini_vlm import GeminiVLM
from src.vision.config import GEMINI_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class VisionPipeline:
    """Run semantic VLM analysis and enforce reliability checks."""

    def __init__(self) -> None:
        # Pass configured timeout for Gemini RPCs so we can tune network timeouts
        # via the vision/.env `GEMINI_TIMEOUT_SECONDS` value.
        self.vlm = GeminiVLM(timeout_seconds=float(GEMINI_TIMEOUT_SECONDS))

    def run(self, image_path: str, debug_output_path: str | None = None) -> Dict[str, Any]:
        """
        Pipeline flow:
        1) Load image
        2) Call GeminiVLM
        3) Validate schema
        4) Validate coordinates/confidence
        5) Generate debug overlay
        6) Return structured output
        """
        logger.info("Vision pipeline started image=%s", image_path)

        image = cv2.imread(image_path)
        if image is None:
            logger.error("Failed to load image: %s", image_path)
            safe_empty = build_empty_response(image_path=image_path, image_width=0, image_height=0)
            return {"vision_output": safe_empty, "debug_image": ""}

        image_height, image_width = image.shape[:2]
        logger.info("Loaded image size width=%d height=%d", image_width, image_height)

        logger.info("Calling Gemini VLM")
        raw_output = self.vlm.analyze(image_path=image_path, image_width=image_width, image_height=image_height)
        if isinstance(raw_output, dict):
            logger.debug("Gemini raw output keys: %s", sorted(raw_output.keys()))
        vlm_error_type = str(raw_output.get("_vlm_error_type", "")).strip().lower() if isinstance(raw_output, dict) else ""
        try:
            vlm_retry_after = float(raw_output.get("_vlm_retry_after_seconds", 0.0)) if isinstance(raw_output, dict) else 0.0
        except Exception:
            vlm_retry_after = 0.0

        logger.info("Running schema validation")
        schema_validated = validate_schema(
            payload=raw_output,
            image_path=image_path,
            image_width=image_width,
            image_height=image_height,
        )
        logger.info("Schema validation produced %d elements", schema_validated.get("element_count", 0))

        logger.info("Running coordinate/confidence validation")
        cleaned = validate_coordinates(
            payload=schema_validated,
            image_width=image_width,
            image_height=image_height,
        )
        logger.info("Coordinate validation produced %d elements", cleaned.get("element_count", 0))

        if cleaned.get("element_count", 0) <= 0:
            logger.warning("No elements detected after validation; returning safe empty response")
            cleaned = build_empty_response(image_path, image_width, image_height)

        overlay_path = debug_output_path or str(Path(image_path).with_name("debug_detected.png"))
        logger.info("Generating debug overlay: %s", overlay_path)
        try:
            debug_path = generate_overlay(image_path=image_path, payload=cleaned, output_path=overlay_path)
        except Exception:
            logger.exception("Failed to generate debug overlay")
            debug_path = ""

        logger.info(
            "Vision pipeline completed image=%s elements=%d error_type=%s retry_after=%.1f",
            image_path,
            cleaned.get("element_count", 0),
            vlm_error_type or "none",
            vlm_retry_after,
        )
        return {
            "vision_output": cleaned,
            "debug_image": debug_path,
            "vlm_error_type": vlm_error_type,
            "vlm_retry_after_seconds": vlm_retry_after,
        }
