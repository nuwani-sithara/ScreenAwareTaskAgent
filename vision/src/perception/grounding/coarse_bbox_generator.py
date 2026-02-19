"""
Coarse BBox Generator (Detector-Agnostic)

Purpose:
- Generate rough bounding boxes from perception sources
- Acts as adapter between VLM / YOLO / heuristics and BBoxRefiner
"""

import json
import cv2
from pathlib import Path


def generate_coarse_bboxes(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 40, 130)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    h, w = image.shape[:2]
    bboxes = []

    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = bw * bh

        # Keep smaller components to improve UI recall.
        if area < 0.0005 * w * h:
            continue

        bboxes.append({
            "bbox": [
                x / w,
                y / h,
                (x + bw) / w,
                (y + bh) / h
            ],
            "source": "layout",
            "confidence": 0.5
        })

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
