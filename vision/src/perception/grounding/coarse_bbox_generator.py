"""
Coarse BBox Generator (Detector-Agnostic)

Purpose:
- Generate rough UI element bounding boxes from visual cues
- Improve recall for form fields, buttons, and text regions
- Acts as adapter between perception heuristics and BBoxRefiner
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np


def detect_screen_bbox(image: np.ndarray) -> Tuple[int, int, int, int]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 140)
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return (0, 0, w, h)

    image_area = float(w * h)
    best = None
    best_score = -1.0

    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < 0.08 * image_area:
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw < 0.25 * w or bh < 0.25 * h:
            continue

        rect_area = float(bw * bh)
        fill_ratio = area / max(1.0, rect_area)
        center_x = x + bw / 2.0
        center_y = y + bh / 2.0
        center_bias = 1.0 - (
            (abs(center_x - (w / 2.0)) / max(1.0, w / 2.0)) * 0.5
            + (abs(center_y - (h / 2.0)) / max(1.0, h / 2.0)) * 0.5
        )
        score = (rect_area / image_area) * 0.7 + fill_ratio * 0.2 + center_bias * 0.1

        if score > best_score:
            best_score = score
            best = (x, y, x + bw, y + bh)

    if best is None:
        return (0, 0, w, h)

    x1, y1, x2, y2 = best
    pad_x = int((x2 - x1) * 0.01)
    pad_y = int((y2 - y1) * 0.01)
    return (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(w, x2 + pad_x),
        min(h, y2 + pad_y),
    )


def bbox_to_dxdy(
    bbox: Tuple[float, float, float, float],
    screen_bbox: Tuple[float, float, float, float],
) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    sx1, sy1, sx2, sy2 = screen_bbox
    sw = max(1e-9, sx2 - sx1)
    sh = max(1e-9, sy2 - sy1)
    # x from left edge of screen; y from top (for y1) and bottom (for y2).
    dx1 = (x1 - sx1) / sw
    dy_top = (y1 - sy1) / sh
    dx2 = (x2 - sx1) / sw
    dy_bottom = (sy2 - y2) / sh
    return (
        max(0.0, min(1.0, dx1)),
        max(0.0, min(1.0, dy_top)),
        max(0.0, min(1.0, dx2)),
        max(0.0, min(1.0, dy_bottom)),
    )


def dxdy_to_bbox(
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


def bbox_to_dxdy_pixels(
    bbox: Tuple[float, float, float, float],
    screen_bbox: Tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> Tuple[int, int]:
    x1, y1, _, _ = bbox
    sx1, sy1, sx2, sy2 = screen_bbox
    screen_x1 = sx1 * image_width
    screen_y1 = sy1 * image_height
    elem_x1 = x1 * image_width
    elem_y1 = y1 * image_height
    dx = int(round(max(0.0, elem_x1 - screen_x1)))
    dy = int(round(max(0.0, elem_y1 - screen_y1)))
    return dx, dy


def _bbox_iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    x1, y1 = max(ax1, bx1), max(ay1, by1)
    x2, y2 = min(ax2, bx2), min(ay2, by2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = float((x2 - x1) * (y2 - y1))
    a_area = float(max(0, ax2 - ax1) * max(0, ay2 - ay1))
    b_area = float(max(0, bx2 - bx1) * max(0, by2 - by1))
    denom = a_area + b_area - inter
    return inter / denom if denom > 0 else 0.0


def _contained_ratio(inner: Tuple[int, int, int, int], outer: Tuple[int, int, int, int]) -> float:
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    x1, y1 = max(ix1, ox1), max(iy1, oy1)
    x2, y2 = min(ix2, ox2), min(iy2, oy2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = float((x2 - x1) * (y2 - y1))
    i_area = float(max(1, ix2 - ix1) * max(1, iy2 - iy1))
    return inter / i_area


def _dedupe_candidates(
    candidates: List[Dict[str, Any]],
    iou_thr: float = 0.72,
    contain_thr: float = 0.95,
) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    ranked = sorted(
        candidates,
        key=lambda c: (
            float(c["confidence"]),
            c["bbox"][2] - c["bbox"][0],
            c["bbox"][3] - c["bbox"][1],
        ),
        reverse=True,
    )

    kept: List[Dict[str, Any]] = []
    for cand in ranked:
        box = tuple(cand["bbox"])
        skip = False
        for existing in kept:
            ebox = tuple(existing["bbox"])
            if _bbox_iou(box, ebox) >= iou_thr:
                skip = True
                break
            if (
                cand.get("source") != "layout_text"
                and _contained_ratio(box, ebox) >= contain_thr
            ):
                skip = True
                break
        if not skip:
            kept.append(cand)
    return kept


def _collect_contour_candidates(
    mask: np.ndarray,
    image_w: int,
    image_h: int,
    source: str,
    confidence: float,
    min_area_frac: float,
    max_area_frac: float = 0.95,
    min_wh: int = 6,
    max_ar: float = 35.0,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    min_area_px = min_area_frac * image_w * image_h
    max_area_px = max_area_frac * image_w * image_h

    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw < min_wh or bh < min_wh:
            continue
        area = float(bw * bh)
        if area < min_area_px or area > max_area_px:
            continue
        ar = max(bw / max(1.0, bh), bh / max(1.0, bw))
        if ar > max_ar:
            continue

        out.append(
            {
                "bbox": [x, y, x + bw, y + bh],
                "source": source,
                "confidence": confidence,
            }
        )
    return out


def _collect_mser_text_candidates(gray: np.ndarray) -> List[Tuple[int, int, int, int]]:
    # MSER catches text-like blobs and compact UI labels.
    mser = cv2.MSER_create()
    if hasattr(mser, "setMinArea"):
        mser.setMinArea(24)
    if hasattr(mser, "setMaxArea"):
        mser.setMaxArea(16000)
    if hasattr(mser, "setMaxVariation"):
        mser.setMaxVariation(0.35)
    regions, _ = mser.detectRegions(gray)
    boxes: List[Tuple[int, int, int, int]] = []
    for region in regions:
        x, y, bw, bh = cv2.boundingRect(region.reshape(-1, 1, 2))
        if bw < 8 or bh < 7:
            continue
        ar = bw / max(1.0, bh)
        if ar < 1.1 or ar > 24.0:
            continue
        boxes.append((x, y, x + bw, y + bh))
    return boxes


def generate_coarse_bboxes(image, max_boxes: int = 160):
    h, w = image.shape[:2]
    sx1, sy1, sx2, sy2 = detect_screen_bbox(image)
    sw = max(1, sx2 - sx1)
    sh = max(1, sy2 - sy1)
    screen_bbox_norm = (sx1 / w, sy1 / h, sx2 / w, sy2 / h)

    roi = image[sy1:sy2, sx1:sx2]
    if roi.size == 0:
        roi = image
        sx1, sy1, sx2, sy2 = 0, 0, w, h
        sw, sh = w, h
        screen_bbox_norm = (0.0, 0.0, 1.0, 1.0)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.equalizeHist(gray)

    candidates: List[Dict[str, Any]] = []

    # 1) Edge-based blocks: cards, panels, input boundaries.
    edges = cv2.Canny(gray, 35, 135)
    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
        iterations=1,
    )
    candidates.extend(
        _collect_contour_candidates(
            edges,
            image_w=sw,
            image_h=sh,
            source="layout_edge",
            confidence=0.58,
            min_area_frac=0.00022,
            max_ar=30.0,
        )
    )

    # 2) Adaptive-threshold regions: low-contrast controls and text lines.
    adaptive = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        19,
        3,
    )
    adaptive = cv2.morphologyEx(
        adaptive,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        iterations=1,
    )
    candidates.extend(
        _collect_contour_candidates(
            adaptive,
            image_w=sw,
            image_h=sh,
            source="layout_adaptive",
            confidence=0.54,
            min_area_frac=0.00016,
            max_ar=26.0,
        )
    )

    # 3) Line extraction: form fields and button borders.
    horizontal = cv2.morphologyEx(
        adaptive,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, sw // 45), 1)),
    )
    vertical = cv2.morphologyEx(
        adaptive,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, sh // 45))),
    )
    form_lines = cv2.bitwise_or(horizontal, vertical)
    form_lines = cv2.dilate(
        form_lines,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        iterations=1,
    )
    candidates.extend(
        _collect_contour_candidates(
            form_lines,
            image_w=sw,
            image_h=sh,
            source="layout_form",
            confidence=0.62,
            min_area_frac=0.00012,
            max_ar=28.0,
        )
    )

    # 4) MSER text candidates: improves recall for labels and short text runs.
    for x1, y1, x2, y2 in _collect_mser_text_candidates(gray):
        candidates.append(
            {
                "bbox": [x1, y1, x2, y2],
                "source": "layout_text",
                "confidence": 0.60,
            }
        )

    filtered: List[Dict[str, Any]] = []
    for c in candidates:
        x1, y1, x2, y2 = c["bbox"]
        area_frac = ((x2 - x1) * (y2 - y1)) / float(sw * sh)
        src = str(c.get("source", ""))
        if src == "layout_adaptive":
            # Suppress border artifacts and tiny blobs that produce unstable dx/dy.
            if x1 <= 2 or y1 <= 2 or x2 >= (sw - 2) or y2 >= (sh - 2):
                continue
            if area_frac < 0.00020:
                continue
        if area_frac > 0.82 and len(candidates) > 20:
            continue
        filtered.append(c)

    deduped = _dedupe_candidates(filtered, iou_thr=0.70, contain_thr=0.94)
    deduped = sorted(
        deduped,
        key=lambda c: (
            float(c["confidence"]),
            -((c["bbox"][2] - c["bbox"][0]) * (c["bbox"][3] - c["bbox"][1])),
        ),
        reverse=True,
    )[:max_boxes]

    bboxes = []
    for item in deduped:
        x1, y1, x2, y2 = item["bbox"]
        gx1 = (sx1 + x1) / w
        gy1 = (sy1 + y1) / h
        gx2 = (sx1 + x2) / w
        gy2 = (sy1 + y2) / h
        bbox_norm = (gx1, gy1, gx2, gy2)
        dxdy = bbox_to_dxdy(bbox_norm, screen_bbox_norm)
        bbox_norm = dxdy_to_bbox(dxdy, screen_bbox_norm)
        dx, dy = bbox_to_dxdy_pixels(bbox_norm, screen_bbox_norm, w, h)
        bboxes.append(
            {
                "dxdy": list(dxdy),
                "dx": dx,
                "dy": dy,
                "screen_bbox": list(screen_bbox_norm),
                "source": item["source"],
                "confidence": float(item["confidence"]),
            }
        )
    return bboxes

def run(
    image_dir="data/preprocessed_frames",
    output_dir="data/coarse_bboxes"
):
    image_dir = Path(image_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for image_path in image_dir.glob("*.jpg"):
        image = cv2.imread(str(image_path))
        if image is None:
            continue

        bboxes = generate_coarse_bboxes(image)

        out_path = output_dir / f"{image_path.stem}.json"
        with open(out_path, "w") as f:
            json.dump({"bboxes": bboxes}, f, indent=2)

        print(f"[CoarseBBox] Generated {out_path.name}")


if __name__ == "__main__":
    run()
