import cv2
import pytesseract
import math
import numpy as np

# =========================
# VALID 2048 VALUES
# =========================
VALID_VALUES = {
    0, 2, 4, 8, 16, 32, 64,
    128, 256, 512, 1024, 2048
}

def snap_to_2048(val):
    if val <= 0:
        return 0
    return int(2 ** round(math.log2(val)))

def extract_tile_number(tile_img):
    h, w = tile_img.shape[:2]

    # =========================
    # INNER DIGIT CROP
    # =========================
    crop = tile_img[
        int(h * 0.25):int(h * 0.75),
        int(w * 0.25):int(w * 0.75)
    ]

    # =========================
    # PREPROCESS
    # =========================
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

    enhanced = cv2.convertScaleAbs(gray, alpha=3.0, beta=-180)

    _, thresh = cv2.threshold(
        enhanced, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # =========================
    # FIND DIGIT CONTOURS
    # =========================
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    digit_boxes = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if ch > thresh.shape[0] * 0.4:
            digit_boxes.append((x, y, cw, ch))

    if not digit_boxes:
        return ""

    # left → right
    digit_boxes.sort(key=lambda b: b[0])

    digits = ""

    for x, y, cw, ch in digit_boxes:
        digit_crop = thresh[y:y+ch, x:x+cw]

        digit_crop = cv2.copyMakeBorder(
            digit_crop, 10, 10, 10, 10,
            cv2.BORDER_CONSTANT, value=255
        )

        config = "--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789"
        d = pytesseract.image_to_string(digit_crop, config=config)
        d = "".join(c for c in d if c.isdigit())

        if d:
            digits += d

    if digits == "":
        return ""

    val = int(digits)

    if val in VALID_VALUES:
        return str(val)

    return str(snap_to_2048(val))

# =====================================================
# SCORE / BEST SCORE OCR
# =====================================================
def extract_score(image, pad=10) -> str:
    """
    OCR for score & best-score boxes
    """

    padded = cv2.copyMakeBorder(
        image, pad, pad, pad, pad,
        cv2.BORDER_CONSTANT, value=[255, 255, 255]
    )

    gray = cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    _, thresh = cv2.threshold(
        gray, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    config = "--psm 7 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(thresh, config=config)

    return "".join(c for c in text if c.isdigit())
