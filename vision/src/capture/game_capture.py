# src/capture/game_capture.py
"""
Capture screenshots of the 2048 game and save to data/raw_frames/.
Uses mss for fast screen capture.

Usage:
    python src/capture/game_capture.py --interval 1 --limit 200
"""

import argparse
import os
import time
from datetime import datetime
import numpy as np
import cv2
import mss

OUT_DIR = "data/raw_frames"
os.makedirs(OUT_DIR, exist_ok=True)

def capture_loop(interval=1.0, limit=None, crop_box=None):
    """
    interval: seconds between screenshots
    limit: max number of screenshots (None -> infinite)
    crop_box: (top, left, width, height) to crop the saved image (optional)
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor; change if needed
        count = 0
        try:
            while True:
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)  # BGRA
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                if crop_box:
                    top, left, w, h = crop_box
                    frame = frame[top:top+h, left:left+w]

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"game_{timestamp}.jpg"
                path = os.path.join(OUT_DIR, filename)
                cv2.imwrite(path, frame)
                print(f"[Saved] {path}")

                count += 1
                if limit and count >= limit:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Capture stopped by user")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", "-i", type=float, default=1.0, help="seconds between captures")
    parser.add_argument("--limit", "-n", type=int, default=None, help="how many screenshots to capture")
    # crop: top,left,width,height
    parser.add_argument("--crop", "-c", type=int, nargs=4, default=None, help="crop box: top left width height")
    args = parser.parse_args()
    capture_loop(interval=args.interval, limit=args.limit, crop_box=tuple(args.crop) if args.crop else None)
