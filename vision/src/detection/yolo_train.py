from ultralytics import YOLO
import torch
import os

def train_ui_detector():
    # Auto-detect device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load pretrained YOLOv8 small model
    model = YOLO("yolov8s.pt")

    # Correct path to data.yml
    data_path = os.path.join(os.path.dirname(__file__), "../../datasets/UIElements/data.yaml")

    # Start training
    model.train(
        data=data_path,
        epochs=10,        # increase for better results
        imgsz=640,
        batch=8,
        workers=2,
        name="ui_detection_exp",
        device=device
    )

if __name__ == "__main__":
    train_ui_detector()
