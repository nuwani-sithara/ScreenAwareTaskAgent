# src/detection/dataset_prep.py
"""
Prepare dataset folder for YOLO training.

Assumes you have:
  src/detection/data/ui_elements.yaml  -> list of class names (or edit classes below)
  data/preprocessed_frames/           -> images (and optionally .txt labels with same base name)

Generates:
  data/dataset/
      train/images, val/images, test/images
      train/labels, val/labels, test/labels
      data.yaml

Usage:
    python src/detection/dataset_prep.py --val 0.15 --test 0.1
"""

import os
import random
import shutil
import argparse
import yaml

SRC_IMG_DIR = "data/preprocessed_frames"
DST_ROOT = "data/dataset"
UI_YAML = "src/detection/data/ui_elements.yaml"

def load_classes():
    # Expecting ui_elements.yaml with 'names' or a 'names' list. Fallback to simple parse.
    if os.path.exists(UI_YAML):
        with open(UI_YAML, "r") as f:
            try:
                dd = yaml.safe_load(f)
                # ultralytics/roboflow style: names or nc/classes
                if isinstance(dd, dict):
                    if "names" in dd:
                        return dd["names"]
                    if "classes" in dd:
                        return dd["classes"]
                    # maybe labels under 'labels' or top-level list
                    for v in dd.values():
                        if isinstance(v, list):
                            return v
                if isinstance(dd, list):
                    return dd
            except Exception:
                pass
    # Default minimal classes (edit if needed)
    return [
        "tile-2","tile-4","tile-8","tile-16","tile-32","tile-64","tile-128","tile-256","tile-512","tile-1024","tile-2048",
        "new-game-button","score-box","best-score-box","game-board","game-over-text"
    ]

def prepare(val_ratio=0.15, test_ratio=0.1, seed=42):
    imgs = [f for f in sorted(os.listdir(SRC_IMG_DIR)) if f.lower().endswith((".jpg", ".png"))]
    random.seed(seed)
    random.shuffle(imgs)

    n = len(imgs)
    n_test = int(n * test_ratio)
    n_val = int(n * val_ratio)
    test = imgs[:n_test]
    val = imgs[n_test:n_test+n_val]
    train = imgs[n_test+n_val:]

    splits = {"train": train, "val": val, "test": test}
    # create dirs
    for split in splits:
        imgs_dir = os.path.join(DST_ROOT, split, "images")
        labels_dir = os.path.join(DST_ROOT, split, "labels")
        os.makedirs(imgs_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)

    # Copy files
    for split, names in splits.items():
        for fname in names:
            src_img = os.path.join(SRC_IMG_DIR, fname)
            dst_img = os.path.join(DST_ROOT, split, "images", fname)
            shutil.copy2(src_img, dst_img)
            base = os.path.splitext(fname)[0]
            # copy label if exists
            src_lbl = os.path.join(SRC_IMG_DIR, base + ".txt")
            dst_lbl = os.path.join(DST_ROOT, split, "labels", base + ".txt")
            if os.path.exists(src_lbl):
                shutil.copy2(src_lbl, dst_lbl)
            else:
                # create empty label file so YOLO training won't crash if it expects labels
                open(dst_lbl, "a").close()

    # create data.yaml
    classes = load_classes()
    data_yaml = {
        "path": os.path.abspath(DST_ROOT),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "names": classes,
        "nc": len(classes)
    }
    with open(os.path.join(DST_ROOT, "data.yaml"), "w") as f:
        yaml.dump(data_yaml, f)
    print("Dataset prepared at", DST_ROOT)
    print("Classes:", classes)
    print("Total images:", n, "-> train:", len(train), "val:", len(val), "test:", len(test))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.1)
    args = parser.parse_args()
    prepare(val_ratio=args.val, test_ratio=args.test)
