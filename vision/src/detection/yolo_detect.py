import os
import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

# paths (use absolute paths relative to vision/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
preprocessed_folder = os.path.join(BASE_DIR, "data", "preprocessed_frames")
output_img_folder = os.path.join(BASE_DIR, "data", "detected_images")
output_csv_folder = os.path.join(BASE_DIR, "data", "detected_csvs")


def run_detection(model_path=None, conf=0.1, iou=0.5):
    """Run YOLO detection over all images in preprocessed_folder."""
    os.makedirs(output_img_folder, exist_ok=True)
    os.makedirs(output_csv_folder, exist_ok=True)

    if model_path is None:
        model_path = os.path.join(BASE_DIR, "runs", "2048_ui", "yolo_train2", "weights", "best.pt")

    model = YOLO(model_path)

    processed = []

    for img_file in os.listdir(preprocessed_folder):
        if not img_file.lower().endswith((".jpg", ".png", ".jpeg")):
            continue

        img_path = os.path.join(preprocessed_folder, img_file)
        frame = cv2.imread(img_path)
        if frame is None:
            continue

        # run detection
        results = model.predict(frame, conf=conf, iou=iou)[0]

        # draw bounding boxes
        annotated_img = results.plot()

        # save annotated image
        cv2.imwrite(os.path.join(output_img_folder, img_file), annotated_img)

        # save detections to CSV
        detections = []
        for box, cls, confv in zip(results.boxes.xyxy, results.boxes.cls, results.boxes.conf):
            x_min, y_min, x_max, y_max = box.tolist()
            detections.append({
                "class": int(cls),
                "class_name": model.names[int(cls)],
                "confidence": float(confv),
                "x_min": int(x_min),
                "y_min": int(y_min),
                "x_max": int(x_max),
                "y_max": int(y_max)
            })

        csv_path = os.path.join(output_csv_folder, os.path.splitext(img_file)[0] + ".csv")
        pd.DataFrame(detections).to_csv(csv_path, index=False)

        processed.append(img_file)

    return processed


if __name__ == "__main__":
    run_detection()
