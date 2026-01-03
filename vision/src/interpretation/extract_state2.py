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

# Optional if Tesseract not in PATH
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CSV_DIR = "data/detected_csvs"
FRAME_DIR = "data/raw_frames"
OUTPUT_JSON = "data/final_output/vision_data.json"

vision_data = []

csv_files = sorted(os.listdir(CSV_DIR))
frame_id = 1

for csv_file in csv_files:
    frame_name = csv_file.replace(".csv", ".jpg")
    frame_path = os.path.join(FRAME_DIR, frame_name)

    image = cv2.imread(frame_path)
    if image is None:
        continue

    frame_entry = {
        "frame_id": frame_id,
        "elements": {}
    }

    with open(os.path.join(CSV_DIR, csv_file), newline='') as f:
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
                else:
                    def preprocess_for_ocr(img):
                        if img is None or img.size == 0:
                            return img

                        # ensure grayscale
                        if len(img.shape) == 3:
                            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        else:
                            gray = img

                        h, w = gray.shape[:2]
                        # upscale small crops for better OCR
                        scale = 2 if max(h, w) < 300 else 1
                        if scale != 1:
                            gray = cv2.resize(gray, (w * scale, h * scale), interpolation=cv2.INTER_LINEAR)

                        # denoise while keeping edges
                        gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

                        # improve contrast
                        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                        gray = clahe.apply(gray)

                        # adaptive threshold to get clean text
                        try:
                            gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                         cv2.THRESH_BINARY, 11, 2)
                        except Exception:
                            # fallback to Otsu
                            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                        return gray

                    proc = preprocess_for_ocr(cropped)

                    # try a few tesseract configs and pick the best by avg confidence
                    configs = ["--oem 3 --psm 6", "--oem 3 --psm 7", "--oem 3 --psm 11"]
                    best_text = ""
                    best_conf = -1.0

                    for cfg in configs:
                        try:
                            data = pytesseract.image_to_data(proc, config=cfg, output_type=Output.DICT)
                        except Exception:
                            continue

                        # join non-empty words preserving spaces
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

                        # prefer higher avg_conf, tie-breaker by longer text
                        score = (avg_conf, len(text))
                        if avg_conf > best_conf or (avg_conf == best_conf and len(text) > len(best_text)):
                            best_conf = avg_conf
                            best_text = text

                    extracted_text = best_text or ""
                    ocr_confidence = float(best_conf) if best_conf >= 0 else None

                    # fallback to EasyOCR if available and confidence low
                    if (ocr_confidence is None or ocr_confidence < 50) and _easyocr_available and _easyocr_reader is not None:
                        try:
                            e_res = _easyocr_reader.readtext(proc)
                            # e_res: list of (bbox, text, conf)
                            e_texts = [t[1].strip() for t in e_res if t[1].strip()]
                            e_confs = [float(t[2]) for t in e_res if isinstance(t[2], (int, float))]
                            if e_texts:
                                e_text = " ".join(e_texts).strip()
                                e_avg = float(np.mean(e_confs)) if e_confs else None
                                # use EasyOCR result if it seems better
                                if e_avg is None or (ocr_confidence is None) or (e_avg > ocr_confidence):
                                    extracted_text = e_text
                                    ocr_confidence = e_avg
                        except Exception:
                            pass

                    # ensure string
                    extracted_text = extracted_text or ""
                    if 'ocr_confidence' not in locals():
                        ocr_confidence = None

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

os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(final_json, f, indent=4)

print("✅ Vision data with OCR created successfully")
