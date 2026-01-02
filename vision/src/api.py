from fastapi import FastAPI
import threading
import time
import logging
import cv2
import os
import uuid

from src.capture.webcam_capture import start_webcam_stream

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
def webcam_capture_loop(camera_index=0):
    global capture_running, latest_frame, latest_result

    logging.info("Webcam capture loop started")

    try:
        stream = start_webcam_stream(camera_index)

        for frame in stream:
            if not capture_running:
                break

            latest_frame = frame

            # TEMP: Just store frame shape (later OCR / YOLO)
            latest_result = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "frame": {
                    "width": frame.shape[1],
                    "height": frame.shape[0]
                },
                "status": "frame_captured"
            }

            time.sleep(0.1)

    except Exception as e:
        logging.error(f"Webcam error: {e}")

    logging.info("Webcam capture loop stopped")

# -------------------------------
# API Endpoints
# -------------------------------
@app.post("/vision/start")
def start_vision(camera_index: int = 0):
    global capture_running, capture_thread

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
    global capture_running
    capture_running = False
    return {"status": "stopped"}

RAW_FRAMES_DIR = "vision/data/raw_frames"

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