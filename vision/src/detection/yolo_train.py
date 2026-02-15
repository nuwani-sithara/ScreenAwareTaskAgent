# src/detection/yolo_train.py
"""
Train YOLOv8 on prepared dataset.
"""

from ultralytics import YOLO
import argparse
import os

DEFAULT_DATA = "data/dataset2/data.yaml"
DEFAULT_MODEL = "yolov8n.pt"


def train(
    data=DEFAULT_DATA,
    model=DEFAULT_MODEL,
    epochs=50,
    imgsz=640,
    batch=8,
    project_name="2048_ui",
    run_name="yolo_train"
):
    print("Training with:")
    print("  data:", data)
    print("  model:", model)

    # Absolute path to project root
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # vision/runs/<project_name>
    runs_dir = os.path.abspath(
        os.path.join(BASE_DIR, "..", "..", "vision", "runs", project_name)
    )
    os.makedirs(runs_dir, exist_ok=True)

    print("Saving training results to:", runs_dir)

    yolom = YOLO(model)

    yolom.train(
        data=data,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=runs_dir,
        name=run_name
    )

    print(f"Training finished. Check {runs_dir}/{run_name}/ for results.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)

    parser.add_argument("--project", default="2048_ui",
                        help="Folder name under vision/runs/")
    parser.add_argument("--name", default="yolo_train",
                        help="Run name inside the project folder")

    args = parser.parse_args()

    train(
        data=args.data,
        model=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project_name=args.project,
        run_name=args.name
    )
