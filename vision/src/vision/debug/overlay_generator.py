"""Debug overlay generator for visualizing detected interaction points."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import cv2


def generate_overlay(image_path: str, payload: Dict[str, Any], output_path: str = "debug_detected.png") -> str:
    """Draw detected (dx, dy) points and labels, then save a debug image."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")

    elements = payload.get("elements", []) if isinstance(payload, dict) else []
    for element in elements:
        dx = int(element.get("dx", 0))
        dy = int(element.get("dy", 0))
        label = str(element.get("label", "unknown"))
        elem_type = str(element.get("type", "unknown"))
        text = f"{elem_type}:{label}"[:80]

        cv2.circle(image, (dx, dy), 4, (0, 255, 0), thickness=-1)
        cv2.putText(
            image,
            text,
            (max(0, dx - 4), max(15, dy - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )

    out = Path(output_path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), image)
    return str(out)
