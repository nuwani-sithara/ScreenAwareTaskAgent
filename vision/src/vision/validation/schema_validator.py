"""Schema validation for vision JSON payloads."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


_REQUIRED_ROOT_FIELDS = {"image", "image_size", "coordinate_system", "element_count", "elements"}
_REQUIRED_ELEMENT_FIELDS = {
    "id",
    "type",
    "label",
    "description",
    "state",
    "dx",
    "dy",
    "confidence",
    "source",
}


def build_empty_response(image_path: str, image_width: int, image_height: int) -> Dict[str, Any]:
    """Create a safe empty response structure."""
    return {
        "image": image_path,
        "image_size": {"width": int(image_width), "height": int(image_height)},
        "coordinate_system": "pixel",
        "element_count": 0,
        "elements": [],
    }


def validate_schema(payload: Dict[str, Any], image_path: str, image_width: int, image_height: int) -> Dict[str, Any]:
    """
    Ensure required root/element fields exist and element_count is consistent.

    Research note:
    The validation layer is designed to improve reliability for downstream agents.
    """
    if not isinstance(payload, dict):
        logger.warning("Schema validation failed: payload is not a dict")
        return build_empty_response(image_path, image_width, image_height)

    missing_root = _REQUIRED_ROOT_FIELDS - set(payload.keys())
    if missing_root:
        logger.warning("Schema validation: missing root fields %s", sorted(missing_root))

    normalized: Dict[str, Any] = {
        "image": payload.get("image", image_path),
        "image_size": payload.get("image_size", {"width": int(image_width), "height": int(image_height)}),
        "coordinate_system": "pixel",
        "elements": [],
    }

    raw_elements = payload.get("elements", [])
    if not isinstance(raw_elements, list):
        logger.warning("Schema validation: elements is not a list")
        raw_elements = []

    valid_elements: List[Dict[str, Any]] = []
    for idx, element in enumerate(raw_elements):
        if not isinstance(element, dict):
            logger.debug("Dropping non-dict element at index %d", idx)
            continue

        missing_element = _REQUIRED_ELEMENT_FIELDS - set(element.keys())
        if missing_element:
            logger.debug("Dropping element %d due to missing fields: %s", idx, sorted(missing_element))
            continue

        try:
            bbox = element.get("bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                try:
                    bbox_out = [int(round(float(v))) for v in bbox]
                except Exception:
                    bbox_out = None
            else:
                bbox_out = None

            normalized_element = {
                "id": str(element["id"]),
                "type": str(element["type"]),
                "label": str(element["label"]),
                "description": str(element["description"]),
                "state": str(element["state"]),
                "dx": int(round(float(element["dx"]))),
                "dy": int(round(float(element["dy"]))),
                "confidence": float(element["confidence"]),
                "source": str(element["source"]),
            }
            if bbox_out is not None:
                normalized_element["bbox"] = bbox_out

            valid_elements.append(normalized_element)
        except Exception:
            logger.debug("Dropping malformed element at index %d", idx, exc_info=True)

    normalized["elements"] = valid_elements
    normalized["element_count"] = len(valid_elements)
    return normalized
