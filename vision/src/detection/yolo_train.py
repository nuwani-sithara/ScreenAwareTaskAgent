# src/detection/yolo_train.py
"""
Train YOLOv8 on prepared dataset.
"""

from ultralytics import YOLO
import argparse
import os

DEFAULT_DATA = "data/dataset/data.yaml"
DEFAULT_MODEL = "yolov8n.pt"


def train(data=DEFAULT_DATA, model=DEFAULT_MODEL, epochs=50, imgsz=640, batch=8, name="2048_ui"):
    print("Training with:", data, model)

    # Absolute path to the project root
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # vision/runs/train (absolute path)
    runs_dir = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "vision", "runs", "train"))
    os.makedirs(runs_dir, exist_ok=True)

    print("Saving training results to:", runs_dir)

    yolom = YOLO(model)

    yolom.train(
        data=data,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        name=name,
        project=runs_dir   # <-- always correct
    )

    print(f"Training finished. Check {runs_dir}/ for results.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--name", default="2048_ui")

    args = parser.parse_args()

    train(
        data=args.data,
        model=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=args.name
    )
