import cv2
import json
import os

from fixed_layout import (
    TILE_CENTERS,
    SCORE_CENTER,
    BEST_SCORE_CENTER,
    TILE_W, TILE_H,
    SCORE_W, SCORE_H
)

from image_utils import crop_from_center
from ocr_utils import extract_tile_number, extract_score
from state_builder import build_game_state


IMAGE_DIR = "data/detected_images"
OUT_DIR = "data/extracted_json"

os.makedirs(OUT_DIR, exist_ok=True)


def main():
    for img_file in os.listdir(IMAGE_DIR):
        if not img_file.endswith(".jpg"):
            continue

        name = img_file.replace(".jpg", "")
        img_path = os.path.join(IMAGE_DIR, img_file)
        img = cv2.imread(img_path)

        if img is None:
            print(f"❌ Failed to load {img_file}")
            continue

        detections = {
            "tiles": [],
            "score": None,
            "best_score": None,
            "button": None
        }

        # =====================
        # 🔹 TILE OCR + COORDS
        # =====================
        for (row, col), (cx, cy) in TILE_CENTERS.items():
            crop = crop_from_center(img, cx, cy, TILE_W, TILE_H)

            val = extract_tile_number(crop)
            if val == "":
                val = "0"

            x_min = cx - TILE_W // 2
            y_min = cy - TILE_H // 2
            x_max = cx + TILE_W // 2
            y_max = cy + TILE_H // 2

            detections["tiles"].append({
                "row": row,
                "col": col,
                "value": int(val),
                "center_x": cx,
                "center_y": cy,
                "width": TILE_W,
                "height": TILE_H,
                "bbox": [x_min, y_min, x_max, y_max]
            })

            # 🔍 Debug overlay (optional)
            cv2.circle(img, (cx, cy), 3, (0, 0, 255), -1)

        # =====================
        # 🔹 SCORE
        # =====================
        score_crop = crop_from_center(
            img,
            SCORE_CENTER[0],
            SCORE_CENTER[1],
            SCORE_W,
            SCORE_H
        )

        score_val = extract_score(score_crop)

        detections["score"] = {
            "value": int(score_val) if score_val.isdigit() else 0,
            "center_x": SCORE_CENTER[0],
            "center_y": SCORE_CENTER[1],
            "width": SCORE_W,
            "height": SCORE_H,
            "bbox": [
                SCORE_CENTER[0] - SCORE_W // 2,
                SCORE_CENTER[1] - SCORE_H // 2,
                SCORE_CENTER[0] + SCORE_W // 2,
                SCORE_CENTER[1] + SCORE_H // 2
            ]
        }

        # =====================
        # 🔹 BEST SCORE
        # =====================
        best_crop = crop_from_center(
            img,
            BEST_SCORE_CENTER[0],
            BEST_SCORE_CENTER[1],
            SCORE_W,
            SCORE_H
        )

        best_val = extract_score(best_crop)

        detections["best_score"] = {
            "value": int(best_val) if best_val.isdigit() else 0,
            "center_x": BEST_SCORE_CENTER[0],
            "center_y": BEST_SCORE_CENTER[1],
            "width": SCORE_W,
            "height": SCORE_H,
            "bbox": [
                BEST_SCORE_CENTER[0] - SCORE_W // 2,
                BEST_SCORE_CENTER[1] - SCORE_H // 2,
                BEST_SCORE_CENTER[0] + SCORE_W // 2,
                BEST_SCORE_CENTER[1] + SCORE_H // 2
            ]
        }

        # =====================
        # 🔹 BUILD GAME STATE
        # =====================
        game_state = build_game_state(detections)

        with open(os.path.join(OUT_DIR, f"{name}.json"), "w") as f:
            json.dump(game_state, f, indent=4)

        print(f"✅ Extracted {name}")


if __name__ == "__main__":
    main()
