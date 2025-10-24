import cv2
import os
import csv
from ultralytics import YOLO

def run_yolo_element_detection(
    input_dir="E:/research/ScreenAwareTaskAgent/vision/data/raw_frames",
    output_dir="E:/research/ScreenAwareTaskAgent/vision/data/detected_frames",
    model_path="E:/research/ScreenAwareTaskAgent/runs/detect/ui_detection_exp4/weights/best.pt",
    conf_threshold=0.4
):
    # Create output directory if it doesn’t exist
    os.makedirs(output_dir, exist_ok=True)

    print(f"🔍 Loading model from: {model_path}")
    model = YOLO(model_path)

    print(f"📂 Processing images from: {input_dir}")
    for file_name in os.listdir(input_dir):
        if not file_name.lower().endswith((".jpg", ".png", ".jpeg")):
            continue

        img_path = os.path.join(input_dir, file_name)
        img = cv2.imread(img_path)
        if img is None:
            print(f"⚠️ Skipping invalid image: {file_name}")
            continue

        # Run YOLO prediction
        results = model.predict(img, conf=conf_threshold, verbose=False)
        result = results[0]

        # CSV output
        csv_name = os.path.splitext(file_name)[0] + ".csv"
        csv_path = os.path.join(output_dir, csv_name)
        with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Class ID", "Class Name", "Confidence", "Bounding Box"])

            if not result.boxes:
                continue

            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = model.names.get(cls_id, "unknown")

                writer.writerow([cls_id, class_name, round(conf, 2), f"[{x1},{y1},{x2},{y2}]"])

                # Draw box and label
                label = f"{class_name} {conf:.2f}"
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, label, (x1, max(y1 - 10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        output_img = os.path.join(output_dir, file_name)
        cv2.imwrite(output_img, img)
        print(f"✅ Processed {file_name} → {csv_name}")

    print("\n🎉 Detection complete! Check output folder for results.")
    print(f"📁 Output images: {output_dir}")

if __name__ == "__main__":
    run_yolo_element_detection()
