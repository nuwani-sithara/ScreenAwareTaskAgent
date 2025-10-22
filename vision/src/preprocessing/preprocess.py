"""
preprocess.py
Basic image enhancement for OCR readiness (grayscale, denoise, contrast).
"""

import cv2
import os

def preprocess_image(image_path, save_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"⚠️ Skipping invalid image: {image_path}")
        return

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.bilateralFilter(gray, 9, 75, 75)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(blur)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, enhanced)
    print(f"✅ Preprocessed: {save_path}")

def batch_preprocess(input_folder="data/raw_frames", output_folder="data/preprocessed_frames"):
    for file in os.listdir(input_folder):
        if file.endswith(".jpg"):
            preprocess_image(
                os.path.join(input_folder, file),
                os.path.join(output_folder, file)
            )

if __name__ == "__main__":
    batch_preprocess()
