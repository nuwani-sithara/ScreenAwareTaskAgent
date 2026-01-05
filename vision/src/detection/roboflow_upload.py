# src/detection/roboflow_upload.py
"""
Example script to upload images to Roboflow (for annotation or hosting).
Set ROBOFLOW_API_KEY env variable before running.

Usage:
    export ROBOFLOW_API_KEY="your_key"
    python src/detection/roboflow_upload.py --folder data/preprocessed_frames
"""

import os
import argparse
from roboflow import Roboflow

def upload(folder):
    api_key = os.getenv("ROBOFLOW_API_KEY")
    if not api_key:
        raise SystemExit("Set ROBOFLOW_API_KEY environment variable")
    rf = Roboflow(api_key=api_key)
    # replace <WORKSPACE>/<PROJECT> below with your own
    workspace = "<WORKSPACE>"
    project = "<PROJECT>"
    proj = rf.workspace(workspace).project(project)
    for fname in os.listdir(folder):
        if fname.lower().endswith((".jpg", ".png")):
            path = os.path.join(folder, fname)
            print("Uploading:", path)
            proj.upload(path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="data/preprocessed_frames")
    args = parser.parse_args()
    upload(args.folder)
