import cv2
import pandas as pd
import json
import os
from ocr_utils import extract_digits
from state_builder import build_game_state

IMAGE_DIR = "data/detected_images"
CSV_DIR = "data/detected_csvs"
OUT_DIR = "data/extracted_json"

os.makedirs(OUT_DIR, exist_ok=True)

for csv_file in os.listdir(CSV_DIR):
    if not csv_file.endswith(".csv"):
        continue

    name = csv_file.replace(".csv", "")
    image = cv2.imread(f"{IMAGE_DIR}/{name}.jpg")
    df = pd.read_csv(f"{CSV_DIR}/{csv_file}")

    detections = {
        "tiles": [],
        "board": None,
        "score": None,
        "best_score": None,
        "buttons": []
    }

    for _, r in df.iterrows():
        crop = image[int(r.y_min):int(r.y_max), int(r.x_min):int(r.x_max)]

        if r.class_name == "tile":
            val = extract_digits(crop)
            if val.isdigit():
                detections["tiles"].append({
                    "value": int(val),
                    "bbox": [r.x_min, r.y_min, r.x_max, r.y_max]
                })

        elif r.class_name == "board":
            detections["board"] = {
                "bbox": [r.x_min, r.y_min, r.x_max, r.y_max]
            }

        elif r.class_name == "score_box":
            val = extract_digits(crop)
            if val.isdigit():
                detections["score"] = int(val)

        elif r.class_name == "best_score_box":
            val = extract_digits(crop)
            if val.isdigit():
                detections["best_score"] = int(val)

    game_state = build_game_state(detections)

    with open(f"{OUT_DIR}/{name}.json", "w") as f:
        json.dump(game_state, f, indent=4)
