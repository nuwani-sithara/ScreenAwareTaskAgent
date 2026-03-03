from typing import Any, Dict, List, Tuple

import numpy as np

from src.perception.grounding.coarse_bbox_generator import generate_coarse_bboxes
from src.vision.screen_boundary import detect_screen_boundaries


_SOURCE_TO_TYPE = {
    "layout_form": "input_field",
    "layout_text": "text",
    "layout_edge": "image",
    "layout_adaptive": "card",
}


def _dxdy_to_bbox(
    dxdy: Tuple[float, float, float, float],
    screen_bbox: Tuple[float, float, float, float],
) -> Tuple[float, float, float, float]:
    dx1, dy_top, dx2, dy_bottom = dxdy
    sx1, sy1, sx2, sy2 = screen_bbox
    sw = max(1e-9, sx2 - sx1)
    sh = max(1e-9, sy2 - sy1)
    x1 = sx1 + dx1 * sw
    y1 = sy1 + dy_top * sh
    x2 = sx1 + dx2 * sw
    y2 = sy2 - dy_bottom * sh
    return (
        max(0.0, min(1.0, x1)),
        max(0.0, min(1.0, y1)),
        max(0.0, min(1.0, x2)),
        max(0.0, min(1.0, y2)),
    )


def _item_bbox_norm(item: Dict[str, Any]) -> Tuple[float, float, float, float]:
    bbox = item.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return tuple(float(v) for v in bbox)
    dxdy = item.get("dxdy")
    screen_bbox = item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0])
    if isinstance(dxdy, (list, tuple)) and len(dxdy) == 4:
        return _dxdy_to_bbox(
            tuple(float(v) for v in dxdy),
            tuple(float(v) for v in screen_bbox),
        )
    return (0.0, 0.0, 1.0, 1.0)


def _map_type(source: str, bbox_norm: Tuple[float, float, float, float]) -> str:
    x1, y1, x2, y2 = bbox_norm
    w = max(1e-9, x2 - x1)
    h = max(1e-9, y2 - y1)
    ar = w / h
    area = w * h
    mapped = _SOURCE_TO_TYPE.get(source, "unknown")
    if mapped == "input_field":
        # Layout-form heuristics can over-fire on tiny top-bar items.
        if area < 0.0014 and h < 0.045:
            return "icon"
        if ar < 1.2 and area < 0.0035:
            return "icon"
        return "input_field"
    if mapped != "unknown":
        return mapped
    if area <= 0.002:
        return "icon"
    if ar >= 4.0 and h <= 0.08:
        return "navbar"
    if ar <= 0.35 and h >= 0.25:
        return "sidebar"
    if ar >= 2.4 and h <= 0.12:
        return "input_field"
    if 1.1 <= ar <= 2.8 and h <= 0.16:
        return "button"
    if area >= 0.20:
        return "card"
    return "text"


def detect_ui_elements(image: np.ndarray, max_boxes: int = 180) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Detect generic UI elements and return boxes in full-image normalized coordinates.

    Returns:
        elements, margin_left, margin_top
    """
    if image is None or image.size == 0:
        return [], 0, 0

    full_h, full_w = image.shape[:2]
    cropped, margin_left, margin_top = detect_screen_boundaries(image)
    crop_h, crop_w = cropped.shape[:2]
    if crop_h < 2 or crop_w < 2:
        cropped = image
        margin_left = 0
        margin_top = 0
        crop_h, crop_w = full_h, full_w

    coarse = generate_coarse_bboxes(cropped, max_boxes=max(20, int(max_boxes)))
    results: List[Dict[str, Any]] = []
    for item in coarse:
        cx1, cy1, cx2, cy2 = _item_bbox_norm(item)
        fx1 = (cx1 * crop_w + margin_left) / float(full_w)
        fy1 = (cy1 * crop_h + margin_top) / float(full_h)
        fx2 = (cx2 * crop_w + margin_left) / float(full_w)
        fy2 = (cy2 * crop_h + margin_top) / float(full_h)
        bbox = (
            max(0.0, min(1.0, fx1)),
            max(0.0, min(1.0, fy1)),
            max(0.0, min(1.0, fx2)),
            max(0.0, min(1.0, fy2)),
        )
        source = str(item.get("source", "layout"))
        results.append(
            {
                "type": _map_type(source, bbox),
                "bbox": bbox,
                "confidence": float(item.get("confidence", 0.5)),
                "source": "ui_detector",
            }
        )

    return results, margin_left, margin_top
