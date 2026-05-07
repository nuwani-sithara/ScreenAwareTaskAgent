"""Debug overlay generator for visualizing detected interaction points."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import cv2


def generate_overlay(image_path: str, payload: Dict[str, Any], output_path: str = "debug_detected.png") -> str:
    """Draw detected points or boxes and labels, then save a debug image."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")

    screen_bbox = None
    if isinstance(payload, dict):
        root_bbox = payload.get("screen_bbox")
        if isinstance(root_bbox, (list, tuple)) and len(root_bbox) == 4:
            try:
                screen_bbox = tuple(int(round(float(v))) for v in root_bbox)
            except Exception:
                screen_bbox = None

    if screen_bbox is not None:
        cv2.rectangle(
            image,
            (screen_bbox[0], screen_bbox[1]),
            (screen_bbox[2], screen_bbox[3]),
            (0, 0, 255),
            2,
        )
        cv2.putText(
            image,
            "screen",
            (max(0, screen_bbox[0]), max(15, screen_bbox[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )

    elements = payload.get("elements", []) if isinstance(payload, dict) else []
    occupied_labels = []

    def _intersects(a, b) -> bool:
        return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

    def _draw_label(text: str, anchor_x: int, anchor_y: int, color) -> None:
        if not text:
            return
        (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        pad_x = 4
        pad_y = 3
        label_w = tw + pad_x * 2
        label_h = th + baseline + pad_y * 2
        x = max(0, min(image.shape[1] - label_w - 1, anchor_x))
        y = max(label_h, min(image.shape[0] - 1, anchor_y))
        rect = [x, y - label_h, x + label_w, y]

        # If the preferred position collides with existing labels, step downward
        # a few times to keep dense clusters readable.
        attempts = 0
        while attempts < 8 and any(_intersects(rect, existing) for existing in occupied_labels):
            y = min(image.shape[0] - 1, y + label_h + 2)
            if y >= image.shape[0] - 1:
                y = label_h
            rect = [x, y - label_h, x + label_w, y]
            attempts += 1

        occupied_labels.append(rect)
        cv2.rectangle(image, (rect[0], rect[1]), (rect[2], rect[3]), (10, 18, 28), thickness=-1)
        cv2.rectangle(image, (rect[0], rect[1]), (rect[2], rect[3]), color, thickness=1)
        cv2.putText(
            image,
            text,
            (rect[0] + pad_x, rect[3] - pad_y - baseline),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )

    for element in elements:
        dx = int(element.get("dx", 0))
        dy = int(element.get("dy", 0))
        label = str(element.get("label", "unknown"))
        elem_type = str(element.get("type", "unknown"))
        text = f"{elem_type}:{label}"[:80]

        bbox = element.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                x1 = int(round(float(bbox[0])))
                y1 = int(round(float(bbox[1])))
                x2 = int(round(float(bbox[2])))
                y2 = int(round(float(bbox[3])))
                if screen_bbox is not None:
                    x1 += screen_bbox[0]
                    y1 += screen_bbox[1]
                    x2 += screen_bbox[0]
                    y2 += screen_bbox[1]
                    dx += screen_bbox[0]
                    dy += screen_bbox[1]
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(image, (dx, dy), 4, (0, 255, 0), thickness=-1)
                _draw_label(text, max(0, x1), max(15, y1 - 6), (0, 255, 0))
                continue
            except Exception:
                pass

        if screen_bbox is not None:
            dx += screen_bbox[0]
            dy += screen_bbox[1]
        cv2.circle(image, (dx, dy), 4, (0, 255, 0), thickness=-1)
        _draw_label(text, max(0, dx - 4), max(15, dy - 6), (0, 255, 0))

    out = Path(output_path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), image)
    return str(out)
