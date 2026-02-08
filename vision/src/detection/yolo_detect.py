import os
import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO
from typing import Optional, List, Dict

# paths (use absolute paths relative to vision/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_PREPRO = os.path.join(BASE_DIR, "data", "preprocessed_frames")
DEFAULT_OUT_IMG = os.path.join(BASE_DIR, "data", "detected_images")
DEFAULT_OUT_CSV = os.path.join(BASE_DIR, "data", "detected_csvs")


def run_detection_single(image_path: str, model_path: Optional[str] = None, 
                         conf: float = 0.1, iou: float = 0.5) -> Dict:
    """
    Run YOLO detection on a single image.
    
    Args:
        image_path: Path to image file
        model_path: Path to YOLO model weights
        conf: Confidence threshold
        iou: NMS IOU threshold
    
    Returns:
        Dict with detections in normalized coordinates
    """
    if model_path is None:
        model_path = os.path.join(BASE_DIR, "runs", "2048_ui", "yolo_train2", "weights", "best.pt")
    
    model = YOLO(model_path)
    
    frame = cv2.imread(image_path)
    if frame is None:
        raise ValueError(f"Failed to read image: {image_path}")
    
    height, width = frame.shape[:2]
    
    # Run detection
    results = model.predict(frame, conf=conf, iou=iou)[0]
    
    # Convert to normalized coordinates
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
            "y_max": int(y_max),
            # Normalized coordinates
            "x_min_norm": x_min / width,
            "y_min_norm": y_min / height,
            "x_max_norm": x_max / width,
            "y_max_norm": y_max / height
        })
    
    return {
        "image_path": image_path,
        "image_size": (width, height),
        "detections": detections,
        "num_detections": len(detections)
    }


def run_detection(preprocessed_folder=None, output_img_folder=None, output_csv_folder=None, model_path=None, conf=0.1, iou=0.5):
    """Run YOLO detection over all images in preprocessed_folder and write outputs to output_* folders."""
    preprocessed_folder = preprocessed_folder or DEFAULT_PREPRO
    output_img_folder = output_img_folder or DEFAULT_OUT_IMG
    output_csv_folder = output_csv_folder or DEFAULT_OUT_CSV

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
