"""Debug overlay generator for visualizing detected interaction points.

Coordinate system contract
--------------------------
All coordinates stored in ``frame_bbox`` / ``frame_dx`` / ``frame_dy`` are
already in **full camera-frame pixel space** (global).  ``bbox`` and ``dx`` /
``dy`` are **screen-crop-local** (relative to the detected screen region).

The overlay draws on the full preprocessed frame, so it must always use
global coordinates.  Priority order for rectangle drawing:
    1. ``frame_bbox``  — already global, use directly.
    2. ``bbox`` + ``screen_bbox`` offset  — screen-local → global.
    3. Nothing (skip rectangle, fall through to dot-only).

Priority order for centre-dot drawing:
    1. ``frame_dx`` / ``frame_dy``  — already global.
    2. ``dx`` / ``dy`` + ``screen_bbox`` offset  — screen-local → global.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2


def generate_overlay(
    image_path: str,
    payload: Dict[str, Any],
    output_path: str = "debug_detected.png",
) -> str:
    """Draw detected points / boxes / labels, then save a debug image."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")

    img_h, img_w = image.shape[:2]

    # ── screen boundary (already global) ────────────────────────────────────
    screen_bbox: Optional[Tuple[int, int, int, int]] = None
    if isinstance(payload, dict):
        root_bbox = payload.get("screen_bbox")
        if isinstance(root_bbox, (list, tuple)) and len(root_bbox) == 4:
            try:
                screen_bbox = tuple(int(round(float(v))) for v in root_bbox)  # type: ignore[assignment]
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

    # ── screen origin (used only when frame_* fields are absent) ────────────
    sx0 = screen_bbox[0] if screen_bbox is not None else 0
    sy0 = screen_bbox[1] if screen_bbox is not None else 0

    # ── elements ────────────────────────────────────────────────────────────
    elements = payload.get("elements", []) if isinstance(payload, dict) else []

    for element in elements:
        label = str(element.get("label", "unknown"))
        elem_type = str(element.get("type", "unknown"))
        text = f"{elem_type}:{label}"[:80]

        # ── resolve global rectangle ─────────────────────────────────────
        draw_rect: Optional[Tuple[int, int, int, int]] = None

        frame_bbox = element.get("frame_bbox")
        if isinstance(frame_bbox, (list, tuple)) and len(frame_bbox) == 4:
            # Priority 1: frame_bbox is already in full-frame pixel space.
            try:
                fx1 = max(0, int(round(float(frame_bbox[0]))))
                fy1 = max(0, int(round(float(frame_bbox[1]))))
                fx2 = min(img_w, int(round(float(frame_bbox[2]))))
                fy2 = min(img_h, int(round(float(frame_bbox[3]))))
                if fx2 > fx1 and fy2 > fy1:
                    draw_rect = (fx1, fy1, fx2, fy2)
            except Exception:
                pass

        if draw_rect is None:
            # Priority 2: screen-local bbox + screen origin → global.
            bbox = element.get("bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                try:
                    bx1 = max(0, int(round(float(bbox[0]))) + sx0)
                    by1 = max(0, int(round(float(bbox[1]))) + sy0)
                    bx2 = min(img_w, int(round(float(bbox[2]))) + sx0)
                    by2 = min(img_h, int(round(float(bbox[3]))) + sy0)
                    if bx2 > bx1 and by2 > by1:
                        draw_rect = (bx1, by1, bx2, by2)
                except Exception:
                    pass

        # ── resolve global centre dot ────────────────────────────────────
        dot_x: Optional[int] = None
        dot_y: Optional[int] = None

        fdx = element.get("frame_dx")
        fdy = element.get("frame_dy")
        if fdx is not None and fdy is not None:
            # Priority 1: frame_dx/dy already global.
            try:
                dot_x = max(0, min(img_w - 1, int(round(float(fdx)))))
                dot_y = max(0, min(img_h - 1, int(round(float(fdy)))))
            except Exception:
                pass

        if dot_x is None:
            # Priority 2: screen-local dx/dy + screen origin → global.
            try:
                raw_dx = int(element.get("dx", 0))
                raw_dy = int(element.get("dy", 0))
                dot_x = max(0, min(img_w - 1, raw_dx + sx0))
                dot_y = max(0, min(img_h - 1, raw_dy + sy0))
            except Exception:
                dot_x, dot_y = sx0, sy0

        if dot_x is None:
            dot_x, dot_y = sx0, sy0

        # ── draw ────────────────────────────────────────────────────────
        if draw_rect is not None:
            rx1, ry1, rx2, ry2 = draw_rect
            cv2.rectangle(image, (rx1, ry1), (rx2, ry2), (0, 255, 0), 2)
            cv2.circle(image, (dot_x, dot_y), 4, (0, 255, 0), thickness=-1)
            cv2.putText(
                image,
                text,
                (max(0, rx1), max(15, ry1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )
        else:
            # No bbox available — draw a labelled dot only.
            cv2.circle(image, (dot_x, dot_y), 4, (0, 255, 0), thickness=-1)
            cv2.putText(
                image,
                text,
                (max(0, dot_x - 4), max(15, dot_y - 8)),
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
