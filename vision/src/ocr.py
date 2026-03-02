"""
vision/src/ocr.py

General-purpose OCR utilities for extracting visible text from UI element crops.

Usage
-----
    from ocr import extract_text_from_region

    text = extract_text_from_region(image, bbox=(0.1, 0.2, 0.4, 0.3), w=1920, h=1080)
    # bbox is normalised [x1, y1, x2, y2] in [0, 1] range
    # returns cleaned text string (empty string if no text found)

Caching
-------
Results are cached by a hash of the cropped-region pixels so identical
regions within a session are not re-processed.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process OCR cache: crop_hash -> text
# ---------------------------------------------------------------------------
_ocr_cache: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Backend selection (Tesseract preferred, PaddleOCR as fallback)
# ---------------------------------------------------------------------------
_TESSERACT_OK: Optional[bool] = None   # None = not yet probed
_PADDLE_OK:    Optional[bool] = None


def _probe_tesseract() -> bool:
    global _TESSERACT_OK
    if _TESSERACT_OK is not None:
        return _TESSERACT_OK
    try:
        import pytesseract  # noqa: F401
        pytesseract.get_tesseract_version()
        _TESSERACT_OK = True
    except Exception:
        _TESSERACT_OK = False
    return _TESSERACT_OK


def _probe_paddle() -> bool:
    global _PADDLE_OK
    if _PADDLE_OK is not None:
        return _PADDLE_OK
    try:
        from paddleocr import PaddleOCR  # noqa: F401
        _PADDLE_OK = True
    except Exception:
        _PADDLE_OK = False
    return _PADDLE_OK


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _crop_from_bbox(
    image: np.ndarray,
    bbox: Tuple[float, float, float, float],
    w: int,
    h: int,
    pad_ratio: float = 0.05,
) -> np.ndarray:
    """Return a pixel crop for a normalised bbox, with optional padding."""
    x1, y1, x2, y2 = bbox
    # Add a small pad to catch glyphs that touch the bbox boundary
    pw = max(0.0, x2 - x1) * pad_ratio
    ph = max(0.0, y2 - y1) * pad_ratio
    px1 = max(0, int((x1 - pw) * w))
    py1 = max(0, int((y1 - ph) * h))
    px2 = min(w, int((x2 + pw) * w))
    py2 = min(h, int((y2 + ph) * h))
    if px2 <= px1 or py2 <= py1:
        return np.zeros((1, 1, 3), dtype=np.uint8)
    return image[py1:py2, px1:px2]


def _preprocess_for_ocr(crop: np.ndarray) -> np.ndarray:
    """
    Upscale and binarise a crop for best OCR accuracy.
    """
    if crop.size == 0:
        return crop
    h, w = crop.shape[:2]

    # Upscale small crops so Tesseract doesn't misread tiny text
    min_side = 48
    if min(h, w) < min_side:
        scale = float(min_side) / float(max(1, min(h, w)))
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        crop = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop

    # Denoise before thresholding
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Adaptive threshold works well for varying backgrounds
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15, 8,
    )
    return binary


def _hash_crop(crop: np.ndarray) -> str:
    """Compute a fast SHA-256 hash of the crop pixels for caching."""
    return hashlib.sha256(crop.tobytes()).hexdigest()[:32]


def _clean_ocr_text(raw: str) -> str:
    """
    Clean raw OCR output:
    - strip leading/trailing whitespace
    - collapse internal runs of whitespace to a single space
    - remove non-printable control characters
    """
    if not raw:
        return ""
    cleaned = "".join(ch if ch.isprintable() else " " for ch in raw)
    return " ".join(cleaned.split())


# ---------------------------------------------------------------------------
# Tesseract OCR backend
# ---------------------------------------------------------------------------

def _run_tesseract(preprocessed: np.ndarray) -> str:
    import pytesseract
    # PSM 7 = single text line; PSM 6 = uniform block of text
    for psm in (7, 6, 11):
        config = f"--oem 3 --psm {psm}"
        text = pytesseract.image_to_string(preprocessed, config=config)
        cleaned = _clean_ocr_text(text)
        if cleaned:
            return cleaned
    return ""


# ---------------------------------------------------------------------------
# PaddleOCR backend (fallback when Tesseract is unavailable)
# ---------------------------------------------------------------------------

_paddle_instance = None


def _get_paddle():
    global _paddle_instance
    if _paddle_instance is None:
        from paddleocr import PaddleOCR
        _paddle_instance = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
    return _paddle_instance


def _run_paddle(crop: np.ndarray) -> str:
    ocr = _get_paddle()
    result = ocr.ocr(crop, cls=False)
    if not result or not result[0]:
        return ""
    lines = []
    for line in result[0]:
        if line and len(line) >= 2:
            text_conf = line[1]
            if isinstance(text_conf, (list, tuple)) and len(text_conf) >= 2:
                text, conf = text_conf[0], float(text_conf[1])
                if conf >= 0.4:
                    lines.append(str(text))
    return _clean_ocr_text(" ".join(lines))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text_from_region(
    image: np.ndarray,
    bbox: Tuple[float, float, float, float],
    w: Optional[int] = None,
    h: Optional[int] = None,
) -> str:
    """
    Extract visible text from a UI element region using OCR.

    Parameters
    ----------
    image : np.ndarray
        Full-frame BGR image (full screen, not pre-cropped).
    bbox : (x1, y1, x2, y2)
        Normalised bounding box in [0, 1] range.
    w, h : int, optional
        Image width and height in pixels.  Inferred from *image* when not
        supplied.

    Returns
    -------
    str
        Cleaned OCR text.  Empty string when no text is detected or when
        neither Tesseract nor PaddleOCR is available.
    """
    if image is None or image.size == 0:
        return ""

    img_h, img_w = image.shape[:2]
    w = w or img_w
    h = h or img_h

    crop = _crop_from_bbox(image, bbox, w, h)
    if crop.size == 0:
        return ""

    # Cache check
    crop_hash = _hash_crop(crop)
    if crop_hash in _ocr_cache:
        return _ocr_cache[crop_hash]

    preprocessed = _preprocess_for_ocr(crop)

    text = ""
    if _probe_tesseract():
        try:
            text = _run_tesseract(preprocessed)
        except Exception as exc:
            logger.debug("Tesseract OCR failed: %s", exc)

    if not text and _probe_paddle():
        try:
            text = _run_paddle(crop)
        except Exception as exc:
            logger.debug("PaddleOCR failed: %s", exc)

    if not text:
        logger.debug("No OCR text found for bbox %s", bbox)

    _ocr_cache[crop_hash] = text
    return text


def clear_ocr_cache() -> None:
    """Discard all cached OCR results (useful between sessions)."""
    _ocr_cache.clear()
