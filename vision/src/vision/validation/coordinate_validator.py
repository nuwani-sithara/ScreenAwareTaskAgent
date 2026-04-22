"""Coordinate and confidence validation for pixel-based UI elements."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.vision.config import CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)


def validate_coordinates(payload: Dict[str, Any], image_width: int, image_height: int) -> Dict[str, Any]:
    """
    Keep only elements with valid pixel coordinates and sufficient confidence.

    Research note:
    This reliability gate removes noisy detections before click automation.
    """
    raw_elements = payload.get("elements", [])
    if not isinstance(raw_elements, list):
        payload["elements"] = []
        payload["element_count"] = 0
        return payload

    cleaned: List[Dict[str, Any]] = []
    for element in raw_elements:
        try:
            dx = int(round(float(element.get("dx"))))
            dy = int(round(float(element.get("dy"))))
            confidence = float(element.get("confidence", 0.0))
        except Exception:
            logger.debug("Dropping element with invalid numeric fields", exc_info=True)
            continue

        if confidence < CONFIDENCE_THRESHOLD:
            continue

        if dx < 0 or dx > image_width:
            continue
        if dy < 0 or dy > image_height:
            continue

        element["dx"] = dx
        element["dy"] = dy
        element["confidence"] = max(0.0, min(1.0, confidence))

        bbox = element.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                x1 = int(round(float(bbox[0])))
                y1 = int(round(float(bbox[1])))
                x2 = int(round(float(bbox[2])))
                y2 = int(round(float(bbox[3])))
                element["bbox"] = [
                    max(0, min(image_width - 1, x1)),
                    max(0, min(image_height - 1, y1)),
                    max(0, min(image_width, x2)),
                    max(0, min(image_height, y2)),
                ]
            except Exception:
                element.pop("bbox", None)

        cleaned.append(element)

    payload["elements"] = cleaned
    payload["element_count"] = len(cleaned)
    return payload
