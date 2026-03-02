from typing import Tuple

import cv2
import numpy as np


def detect_screen_boundaries(image: np.ndarray) -> Tuple[np.ndarray, int, int]:
    """
    Detect actual visible screen region and return cropped image + margins.

    Returns:
        cropped_image, margin_left, margin_top
    """
    if image is None or image.size == 0:
        return image, 0, 0

    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Fast dark-border trim to remove webcam framing/letterboxing.
    row_mean = blur.mean(axis=1)
    col_mean = blur.mean(axis=0)
    dark_thr = 16.0
    top = 0
    while top < h - 2 and row_mean[top] < dark_thr:
        top += 1
    bottom = h - 1
    while bottom > 1 and row_mean[bottom] < dark_thr:
        bottom -= 1
    left = 0
    while left < w - 2 and col_mean[left] < dark_thr:
        left += 1
    right = w - 1
    while right > 1 and col_mean[right] < dark_thr:
        right -= 1
    if (bottom - top) >= int(0.55 * h) and (right - left) >= int(0.55 * w):
        pad = 2
        top = max(0, top - pad)
        left = max(0, left - pad)
        bottom = min(h - 1, bottom + pad)
        right = min(w - 1, right + pad)
        cropped = image[top:bottom + 1, left:right + 1]
        if cropped.size > 0:
            return cropped, left, top

    # Non-black mask first; then fallback to strong edges.
    _, non_black = cv2.threshold(blur, 10, 255, cv2.THRESH_BINARY)
    non_black = cv2.morphologyEx(
        non_black,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)),
        iterations=2,
    )

    contours, _ = cv2.findContours(non_black, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(w * h)
    best = None
    best_score = -1.0

    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = float(bw * bh)
        if area < 0.20 * image_area:
            continue
        cx = x + (bw / 2.0)
        cy = y + (bh / 2.0)
        center_bias = 1.0 - (
            (abs(cx - (w / 2.0)) / max(1.0, w / 2.0)) * 0.5
            + (abs(cy - (h / 2.0)) / max(1.0, h / 2.0)) * 0.5
        )
        score = (area / image_area) * 0.85 + center_bias * 0.15
        if score > best_score:
            best_score = score
            best = (x, y, x + bw, y + bh)

    if best is None:
        edges = cv2.Canny(blur, 45, 140)
        edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = float(bw * bh)
            if area > best_score and area >= 0.20 * image_area:
                best_score = area
                best = (x, y, x + bw, y + bh)

    if best is None:
        return image, 0, 0

    x1, y1, x2, y2 = best
    x1 = max(0, min(w - 1, x1))
    y1 = max(0, min(h - 1, y1))
    x2 = max(x1 + 1, min(w, x2))
    y2 = max(y1 + 1, min(h, y2))
    cropped = image[y1:y2, x1:x2]
    return cropped, x1, y1
