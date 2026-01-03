from fastapi import FastAPI
import threading
import time
import logging
import cv2
import os
import uuid

from src.capture.webcam_capture import start_webcam_stream
import json
from src.preprocessing.preprocess import preprocess_all
from src.detection.yolo_detect import run_detection
from src.interpretation.extract_state2 import run_extraction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
) 

app = FastAPI(title="Vision Service")

# -------------------------------
# Global state
# -------------------------------
capture_running = False
capture_thread = None
latest_frame = None
latest_result = {}

# -------------------------------
# Webcam capture loop
# -------------------------------
def webcam_capture_loop(camera_index=0, save_interval=1.0):
    """Stream frames and save snapshots to RAW_FRAMES_DIR periodically."""
    global capture_running, latest_frame, latest_result

    logging.info("Webcam capture loop started")

    os.makedirs(RAW_FRAMES_DIR, exist_ok=True)
    last_saved = 0.0

    try:
        stream = start_webcam_stream(camera_index)

        for frame in stream:
            if not capture_running:
                break

            latest_frame = frame
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            latest_result = {
                "timestamp": timestamp,
                "frame": {
                    "width": frame.shape[1],
                    "height": frame.shape[0]
                },
                "status": "frame_captured"
            }

            now = time.time()
            if now - last_saved >= save_interval:
                # Unique filename
                filename = f"frame_{int(now)}_{uuid.uuid4().hex[:6]}.jpg"
                filepath = os.path.join(RAW_FRAMES_DIR, filename)

                # Save frame
                cv2.imwrite(filepath, frame)
                logging.info(f"💾 Frame saved: {filepath}")

                last_saved = now

            time.sleep(0.1)

    except Exception as e:
        logging.error(f"Webcam error: {e}")

    logging.info("Webcam capture loop stopped")

# -------------------------------
# API Endpoints
# -------------------------------
@app.post("/vision/start")
def start_vision():
    """Start webcam capture (enforce camera_index=0)."""
    global capture_running, capture_thread

    camera_index = 0  # always use index 0 for the webcam

    if capture_running:
        return {"status": "already_running"}

    capture_running = True
    capture_thread = threading.Thread(
        target=webcam_capture_loop,
        args=(camera_index,),
        daemon=True
    )
    capture_thread.start()

    return {"status": "started", "camera_index": camera_index}


@app.post("/vision/stop")
def stop_vision():
    """Stop capture, then run preprocessing -> detection -> extraction and return final JSON."""
    global capture_running, capture_thread

    if not capture_running:
        return {"status": "not_running"}

    capture_running = False

    # Wait briefly for thread to finish
    if capture_thread and capture_thread.is_alive():
        capture_thread.join(timeout=10)

    # Check we have captured frames
    captured_files = [f for f in os.listdir(RAW_FRAMES_DIR) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
    if not captured_files:
        return {"status": "no_frames_captured"}

    try:
        logging.info("Starting preprocessing...")
        preprocess_all()

        logging.info("Running detection...")
        processed = run_detection()

        logging.info("Extracting final JSON...")
        out_path = run_extraction()

        # Read and return the JSON content
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {"status": "completed", "vision_data": data}

    except Exception as e:
        logging.exception("Vision pipeline failed")
        return {"status": "error", "detail": str(e)}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW_FRAMES_DIR = os.path.join(BASE_DIR, "data", "raw_frames")

@app.post("/vision/capture")
def capture_once():
    global latest_frame, latest_result

    if latest_frame is None:
        return {"status": "no_frame_available"}

    os.makedirs(RAW_FRAMES_DIR, exist_ok=True)

    # Unique filename
    filename = f"frame_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
    filepath = os.path.join(RAW_FRAMES_DIR, filename)

    # Save frame
    cv2.imwrite(filepath, latest_frame)

    logging.info(f"💾 Frame saved: {filepath}")

    # Attach path to response
    response = latest_result.copy()
    response["saved_frame"] = filepath

    return response