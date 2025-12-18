import os
import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

# paths
preprocessed_folder = "data/preprocessed_frames"
output_img_folder = "data/detected_images"
output_csv_folder = "data/detected_csvs"

os.makedirs(output_img_folder, exist_ok=True)
os.makedirs(output_csv_folder, exist_ok=True)

# load model
model = YOLO("runs/train/2048_ui/weights/best.pt")

# process each image
for img_file in os.listdir(preprocessed_folder):
    if not img_file.lower().endswith((".jpg", ".png", ".jpeg")):
        continue

    img_path = os.path.join(preprocessed_folder, img_file)
    frame = cv2.imread(img_path)

    # run detection with low confidence threshold
    results = model.predict(frame, conf=0.1, iou=0.5)[0]

    # Debug: print detection count
    print("->", img_file, "detections:", len(results.boxes))

    # draw bounding boxes
    annotated_img = results.plot()

    # save annotated image
    cv2.imwrite(os.path.join(output_img_folder, img_file), annotated_img)

    # save detections to CSV
    detections = []
    for box, cls, conf in zip(results.boxes.xyxy, results.boxes.cls, results.boxes.conf):
        x_min, y_min, x_max, y_max = box.tolist()
        detections.append({
            "class": int(cls),
            "class_name": model.names[int(cls)],
            "confidence": float(conf),
            "x_min": int(x_min),
            "y_min": int(y_min),
            "x_max": int(x_max),
            "y_max": int(y_max)
        })

    csv_path = os.path.join(output_csv_folder, os.path.splitext(img_file)[0] + ".csv")
    pd.DataFrame(detections).to_csv(csv_path, index=False)

    print(f"Processed {img_file}: {len(detections)} detections")
