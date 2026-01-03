# src/preprocessing/preprocess.py
"""
Preprocess images in data/raw_frames -> data/preprocessed_frames.
Crop/resize/convert if needed.

Usage:
    python src/preprocessing/preprocess.py --crop 100 300 800 800 --resize 640
"""

import os
import cv2
import argparse

import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_RAW_DIR = os.path.join(BASE_DIR, "data", "raw_frames")
DEFAULT_OUT_DIR = os.path.join(BASE_DIR, "data", "preprocessed_frames")


def preprocess_all(raw_dir=None, out_dir=None, crop=None, resize=None, ext_in=(".jpg", ".png")):
    """Preprocess all images found in raw_dir and write to out_dir.

    If raw_dir or out_dir are None, defaults inside data/ are used.
    """
    raw_dir = raw_dir or DEFAULT_RAW_DIR
    out_dir = out_dir or DEFAULT_OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    files = [f for f in sorted(os.listdir(raw_dir)) if f.lower().endswith(ext_in)]
    for fname in files:
        path = os.path.join(raw_dir, fname)
        img = cv2.imread(path)
        if img is None:
            print("Skipping (not an image):", path)
            continue

        if crop:
            crop_w, crop_h = crop  # width, height
            H, W = img.shape[:2]

            # compute centered crop
            left = (W - crop_w) // 2
            top = (H - crop_h) // 2

            # ensure boundaries are valid
            left = max(left, 0)
            top = max(top, 0)
            right = min(left + crop_w, W)
            bottom = min(top + crop_h, H)

            img = img[top:bottom, left:right]

        if resize:
            h, w = img.shape[:2]
            # preserve aspect ratio: set max dim to resize
            scale = resize / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        out_path = os.path.join(out_dir, fname)
        cv2.imwrite(out_path, img)
        print("Wrote:", out_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--crop", nargs=2, type=int, help="center crop: width height")
    parser.add_argument("--resize", type=int, help="max dimension (e.g. 640)")
    args = parser.parse_args()

    preprocess_all(crop=tuple(args.crop) if args.crop else None, resize=args.resize)
