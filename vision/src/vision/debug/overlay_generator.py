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

    elements = payload.get("elements", []) if isinstance(payload, dict) else []
    occupied_labels = []

    def _intersects(a, b) -> bool:
        return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

    def _draw_label(text: str, anchor_x: int, anchor_y: int, color) -> None:
        if not text:
            return
        (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        pad_x, pad_y = 4, 3
        label_w = tw + pad_x * 2
        label_h = th + baseline + pad_y * 2
        x = max(0, min(image.shape[1] - label_w - 1, anchor_x))
        y = max(label_h, min(image.shape[0] - 1, anchor_y))
        rect = [x, y - label_h, x + label_w, y]

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
        # frame_dx/frame_dy and frame_bbox are already absolute pixel coords
        # produced by _finalize_elements_with_dxdy. Use them directly.
        # Fall back to dx/dy only if frame_* fields are absent (legacy path).
        frame_dx = element.get("frame_dx") or element.get("dx", 0)
        frame_dy = element.get("frame_dy") or element.get("dy", 0)
        try:
            cx = int(round(float(frame_dx)))
            cy = int(round(float(frame_dy)))
        except Exception:
            cx, cy = 0, 0

        label = str(element.get("label", "unknown"))
        elem_type = str(element.get("type", "unknown"))
        text = f"{elem_type}:{label}"[:80]

        # Prefer frame_bbox (absolute pixels set by finalize), fall back to bbox.
        # Never add screen_bbox offsets here — frame_bbox/frame_dx/frame_dy are
        # already in absolute screen pixel space.
        raw_bbox = element.get("frame_bbox") or element.get("bbox")
        drew_box = False

        if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
            try:
                x1, y1, x2, y2 = (int(round(float(v))) for v in raw_bbox)
                img_h, img_w = image.shape[:2]
                x1 = max(0, min(img_w - 1, x1))
                y1 = max(0, min(img_h - 1, y1))
                x2 = max(0, min(img_w, x2))
                y2 = max(0, min(img_h, y2))
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(image, (cx, cy), 4, (0, 255, 0), thickness=-1)
                _draw_label(text, x1, max(15, y1 - 6), (0, 255, 0))
                drew_box = True
            except Exception:
                pass

        if not drew_box:
            cv2.circle(image, (cx, cy), 4, (0, 255, 0), thickness=-1)
            _draw_label(text, max(0, cx - 4), max(15, cy - 6), (0, 255, 0))

    out = Path(output_path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), image)
    return str(out)