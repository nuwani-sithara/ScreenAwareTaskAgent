import hashlib
import re
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

_OCR_CACHE: Dict[str, str] = {}
_PYTESSERACT = None
_EASYOCR_READER = None
_PADDLE_READER = None


def _init_backends() -> None:
    global _PYTESSERACT, _EASYOCR_READER, _PADDLE_READER
    if _PYTESSERACT is None:
        try:
            import pytesseract  # type: ignore
            _PYTESSERACT = pytesseract
        except Exception:
            _PYTESSERACT = False
    if _EASYOCR_READER is None:
        try:
            import easyocr  # type: ignore
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=False)
        except Exception:
            _EASYOCR_READER = False
    if _PADDLE_READER is None:
        try:
            from paddleocr import PaddleOCR  # type: ignore
            _PADDLE_READER = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        except Exception:
            _PADDLE_READER = False


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"[^\w\s\-\./:@#%&()+]", "", text)
    return text.strip()


def _to_pixel_bbox(
    bbox: Tuple[float, float, float, float],
    width: int,
    height: int,
) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    px1 = max(0, min(width - 1, int(round(x1 * width))))
    py1 = max(0, min(height - 1, int(round(y1 * height))))
    px2 = max(px1 + 1, min(width, int(round(x2 * width))))
    py2 = max(py1 + 1, min(height, int(round(y2 * height))))
    return px1, py1, px2, py2


def _region_hash(image: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(image.tobytes())
    return h.hexdigest()


def extract_text_from_region(
    image: np.ndarray,
    bbox: Tuple[float, float, float, float],
) -> str:
    """
    Crop region using bbox, run OCR, clean and return extracted text.
    """
    if image is None or image.size == 0:
        return ""

    h, w = image.shape[:2]
    x1, y1, x2, y2 = _to_pixel_bbox(bbox, w, h)
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return ""

    key = _region_hash(crop)
    if key in _OCR_CACHE:
        return _OCR_CACHE[key]

    _init_backends()
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    proc = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        9,
    )

    best = ""
    if _PYTESSERACT not in (None, False):
        try:
            txt = _PYTESSERACT.image_to_string(proc, config="--psm 6")
            best = _clean_text(txt)
        except Exception:
            pass

    if not best and _EASYOCR_READER not in (None, False):
        try:
            vals = _EASYOCR_READER.readtext(proc)
            parts = [str(v[1]) for v in vals if isinstance(v, (list, tuple)) and len(v) >= 2]
            best = _clean_text(" ".join(parts))
        except Exception:
            pass

    if not best and _PADDLE_READER not in (None, False):
        try:
            vals = _PADDLE_READER.ocr(proc, cls=True)
            parts = []
            for line in vals or []:
                for token in line or []:
                    if isinstance(token, (list, tuple)) and len(token) >= 2 and isinstance(token[1], (list, tuple)):
                        parts.append(str(token[1][0]))
            best = _clean_text(" ".join(parts))
        except Exception:
            pass

    _OCR_CACHE[key] = best
    return best

