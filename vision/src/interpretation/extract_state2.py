import os
import csv
import json
import cv2
import pytesseract
from pytesseract import Output
import numpy as np

# optional EasyOCR fallback
try:
    import easyocr
    _easyocr_available = True
except Exception:
    easyocr = None
    _easyocr_available = False

# create one EasyOCR reader instance to avoid repeated initialization messages
_easyocr_reader = None
if _easyocr_available:
    try:
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
    except Exception:
        _easyocr_reader = None
        _easyocr_available = False

# optional PaddleOCR fallback
try:
    from paddleocr import PaddleOCR
    _paddleocr_available = True
except Exception:
    PaddleOCR = None
    _paddleocr_available = False

# create one PaddleOCR reader (CPU) if available
_paddleocr_reader = None
if _paddleocr_available:
    try:
        _paddleocr_reader = PaddleOCR(use_angle_cls=True, lang='en')
    except Exception:
        _paddleocr_reader = None
        _paddleocr_available = False

# --- OCR helper utilities ---

def expand_bbox(x_min, y_min, x_max, y_max, img_w, img_h, pad=0.12):
    pad_w = int((x_max - x_min) * pad)
    pad_h = int((y_max - y_min) * pad)
    nx_min = max(0, x_min - pad_w)
    ny_min = max(0, y_min - pad_h)
    nx_max = min(img_w, x_max + pad_w)
    ny_max = min(img_h, y_max + pad_h)
    return nx_min, ny_min, nx_max, ny_max


def deskew(img):
    # expects a binary or grayscale image
    try:
        coords = np.column_stack(np.where(img > 0))
        if coords.shape[0] < 10:
            return img
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        return img


def unsharp_mask(img):
    try:
        blur = cv2.GaussianBlur(img, (0, 0), sigmaX=1.0)
        return cv2.addWeighted(img, 1.5, blur, -0.5, 0)
    except Exception:
        return img


def preprocess_for_ocr(img):
    """Return a dict of preprocessing variants to try for OCR."""
    if img is None or img.size == 0:
        return {}

    # ensure color -> gray
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # upscale small crops
    h0, w0 = gray.shape[:2]
    scale = 2 if max(h0, w0) < 300 else 1
    if scale != 1:
        gray = cv2.resize(gray, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_CUBIC)

    # denoise + contrast
    gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # sharpen
    gray = unsharp_mask(gray)

    variants = {"orig": gray}

    # adaptive threshold
    try:
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    except Exception:
        _, adaptive = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants["adaptive"] = adaptive

    # otsu
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants["otsu"] = otsu

    # deskew variants (on binary)
    try:
        variants["deskewed"] = deskew(otsu)
    except Exception:
        pass

    return variants


def run_tesseract_variants(proc_variants, class_name):
    """Run Tesseract over multiple preprocessed variants and configs; return best text and avg confidence."""
    configs = ["--oem 3 --psm 6", "--oem 3 --psm 7", "--oem 3 --psm 11"]

    # class-specific whitelist (optional)
    whitelist_map = {
        "login_button": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "title_text": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:.-_ ",
        "username_input": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@._- "
    }

    best_text = ""
    best_conf = -1.0

    for name, proc in proc_variants.items():
        for cfg in configs:
            cfg_str = cfg
            wl = whitelist_map.get(class_name)
            if wl:
                cfg_str = cfg_str + f" -c tessedit_char_whitelist={wl}"

            try:
                data = pytesseract.image_to_data(proc, config=cfg_str, output_type=Output.DICT)
            except Exception:
                continue

            words = [w for w in data.get('text', []) if str(w).strip()]
            text = " ".join(words).strip()

            confs = []
            for c in data.get('conf', []):
                try:
                    ci = float(c)
                    if ci >= 0:
                        confs.append(ci)
                except Exception:
                    continue

            avg_conf = float(np.mean(confs)) if confs else -1.0

            if avg_conf > best_conf or (avg_conf == best_conf and len(text) > len(best_text)):
                best_conf = avg_conf
                best_text = text

    return best_text, (best_conf if best_conf >= 0 else None)

# Optional if Tesseract not in PATH
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_CSV_DIR = os.path.join(BASE_DIR, "data", "detected_csvs")
DEFAULT_FRAME_DIR = os.path.join(BASE_DIR, "data", "raw_frames")


def run_extraction(csv_dir=None, frame_dir=None, output_json=None):
    """Process CSV detections and produce a final JSON placed at output_json."""
    csv_dir = csv_dir or DEFAULT_CSV_DIR
    frame_dir = frame_dir or DEFAULT_FRAME_DIR
    output_json = output_json or os.path.join(BASE_DIR, "data", "final_output", "vision_data.json")

    vision_data = []

    csv_files = sorted(os.listdir(csv_dir))
    frame_id = 1

    for csv_file in csv_files:
        frame_name = csv_file.replace(".csv", ".jpg")
        frame_path = os.path.join(frame_dir, frame_name)

        image = cv2.imread(frame_path)
        if image is None:
            continue

        frame_entry = {
            "frame_id": frame_id,
            "elements": {}
        }

        with open(os.path.join(csv_dir, csv_file), newline='') as f:
            reader = csv.DictReader(f)

            for row in reader:
                class_name = row["class_name"]

                x_min = int(row["x_min"])
                y_min = int(row["y_min"])
                x_max = int(row["x_max"])
                y_max = int(row["y_max"])

                cropped = image[y_min:y_max, x_min:x_max]

                extracted_text = ""
                ocr_confidence = None

                # OCR only where meaningful
                if class_name in ["title_text", "login_button", "username_input"]:
                    # skip if crop is empty
                    if cropped is None or cropped.size == 0:
                        extracted_text = ""
                        ocr_confidence = None
                    else:
                        # expand bbox to avoid clipped text
                        img_h, img_w = image.shape[:2]
                        nx_min, ny_min, nx_max, ny_max = expand_bbox(x_min, y_min, x_max, y_max, img_w, img_h, pad=0.12)
                        cropped_exp = image[ny_min:ny_max, nx_min:nx_max]

                        # get preprocessing variants
                        proc_variants = preprocess_for_ocr(cropped_exp)

                        # run Tesseract variants
                        best_text, best_conf = run_tesseract_variants(proc_variants, class_name)

                        extracted_text = best_text or ""
                        ocr_confidence = float(best_conf) if best_conf is not None else None

                        # fallback to EasyOCR if available and confidence low
                        if (ocr_confidence is None or ocr_confidence < 50) and _easyocr_available and _easyocr_reader is not None:
                            try:
                                # use the 'orig' variant if available
                                easy_img = proc_variants.get('orig') if proc_variants.get('orig') is not None else cropped_exp
                                e_res = _easyocr_reader.readtext(easy_img)
                                e_texts = [t[1].strip() for t in e_res if t[1].strip()]
                                e_confs = [float(t[2]) for t in e_res if isinstance(t[2], (int, float))]
                                if e_texts:
                                    e_text = " ".join(e_texts).strip()
                                    e_avg = float(np.mean(e_confs)) if e_confs else None
                                    if e_avg is None or (ocr_confidence is None) or (e_avg > ocr_confidence):
                                        extracted_text = e_text
                                        ocr_confidence = e_avg
                            except Exception:
                                pass

                    # PaddleOCR fallback if still low confidence and available
                    if (ocr_confidence is None or ocr_confidence < 50) and _paddleocr_available and _paddleocr_reader is not None:
                        try:
                            # PaddleOCR returns list of lines: [ [[box coords]], (text, conf) ]
                            paddle_res = _paddleocr_reader.ocr(cropped_exp, cls=True)  # cls=True for angle correction
                            p_texts = []
                            p_confs = []
                            for line in paddle_res:
                                if len(line) >= 2:
                                    # some versions return [[box], (text, conf)] or [[box, ...], [(text, conf)]]; be resilient
                                    candidate = None
                                    confv = None
                                    # try to extract text/conf robustly
                                    if isinstance(line[1], tuple) or isinstance(line[1], list):
                                        candidate = line[1][0]
                                        try:
                                            confv = float(line[1][1])
                                        except Exception:
                                            confv = None
                                    else:
                                        # some versions: [[box], text, conf]
                                        try:
                                            candidate = line[1]
                                        except Exception:
                                            candidate = None
                                    if candidate and str(candidate).strip():
                                        p_texts.append(str(candidate).strip())
                                    if confv is not None:
                                        p_confs.append(confv)
                            if p_texts:
                                p_text = " ".join(p_texts).strip()
                                p_avg = float(np.mean(p_confs)) if p_confs else None
                                if p_avg is None or (ocr_confidence is None) or (p_avg > ocr_confidence):
                                    extracted_text = p_text
                                    ocr_confidence = p_avg
                        except Exception:
                            pass

                # Build element entry for this class
                frame_entry["elements"][class_name] = {
                    "bbox": {
                        "x_min": x_min,
                        "y_min": y_min,
                        "x_max": x_max,
                        "y_max": y_max
                    },
                    "confidence": float(row["confidence"]),
                    "text": extracted_text,
                    "ocr_confidence": ocr_confidence
                }

        vision_data.append(frame_entry)
        frame_id += 1

    final_json = {
        "vision_data": vision_data
    }

    os.makedirs(os.path.dirname(output_json), exist_ok=True)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=4)

    print("✅ Vision data with OCR created successfully")

    return output_json


if __name__ == "__main__":
    run_extraction()
