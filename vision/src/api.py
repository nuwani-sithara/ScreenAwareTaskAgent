from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import threading
import time
import logging
import cv2
import os
import uuid
import queue
import shutil

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
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SESSIONS_DIR = os.path.join(BASE_DIR, "data", "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

capture_running = False
capture_thread = None
latest_frame = None
latest_result = {}
current_session = None  # dict containing session id and folder paths
processing_queue = queue.Queue()
processed_queue = queue.Queue()
processing_thread = None

# -------------------------------
# Webcam capture loop
# -------------------------------
def webcam_capture_loop(camera_index=0, save_dir=None, save_interval=1.0):
    """Stream frames and save snapshots to save_dir periodically, but only when UI changes."""
    global capture_running, latest_frame, latest_result

    logging.info("Webcam capture loop started")

    if save_dir is None:
        logging.error("No save_dir provided to capture loop; exiting.")
        return

    os.makedirs(save_dir, exist_ok=True)
    last_saved = 0.0
    last_saved_small = None
    CHANGE_THRESHOLD = 0.01  # fraction of pixels changed to trigger save

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

            # compute small grayscale representation for quick change detection
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                h, w = gray.shape[:2]
                max_dim = 320
                scale = max_dim / max(h, w) if max(h, w) > max_dim else 1.0
                small = cv2.resize(gray, (int(w * scale), int(h * scale))) if scale != 1.0 else gray

                save_flag = False
                if last_saved_small is None:
                    save_flag = True
                else:
                    diff = cv2.absdiff(small, last_saved_small)
                    _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                    changed = int(cv2.countNonZero(thresh))
                    ratio = changed / float(thresh.size)
                    if ratio >= CHANGE_THRESHOLD:
                        save_flag = True
            except Exception:
                # fallback: if any error in change detection, allow saving by interval
                save_flag = True

            if now - last_saved >= save_interval and save_flag:
                # Unique filename
                filename = f"frame_{int(now)}_{uuid.uuid4().hex[:6]}.jpg"
                filepath = os.path.join(save_dir, filename)

                # Save frame
                cv2.imwrite(filepath, frame)
                logging.info(f"Frame saved: {filepath}")

                # enqueue the saved frame for immediate per-frame processing
                try:
                    processing_queue.put_nowait(filepath)
                except Exception:
                    logging.exception("Failed to enqueue frame for processing")

                last_saved = now
                try:
                    last_saved_small = small.copy()
                except Exception:
                    last_saved_small = None

            time.sleep(0.05)

    except Exception as e:
        logging.error(f"Webcam error: {e}")

    logging.info("Webcam capture loop stopped")


# -------------------------------
# Processing worker: per-frame pipeline
# -------------------------------
def processing_worker():
    """Background worker that processes saved frames one-by-one and pushes JSON to processed_queue."""
    global processing_queue, processed_queue
    logging.info("Processing worker started")
    while True:
        try:
            filepath = processing_queue.get(timeout=1.0)
        except Exception:
            # loop to allow thread to exit if needed
            time.sleep(0.1)
            continue

        try:
            # create a small temporary processing workspace
            proc_id = f"proc_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            proc_root = os.path.join(SESSIONS_DIR, proc_id)
            raw_dir = os.path.join(proc_root, "raw_frames")
            preproc_dir = os.path.join(proc_root, "preprocessed_frames")
            detected_images_dir = os.path.join(proc_root, "detected_images")
            detected_csvs_dir = os.path.join(proc_root, "detected_csvs")
            final_output_dir = os.path.join(proc_root, "final_output")

            os.makedirs(raw_dir, exist_ok=True)
            os.makedirs(preproc_dir, exist_ok=True)
            os.makedirs(detected_images_dir, exist_ok=True)
            os.makedirs(detected_csvs_dir, exist_ok=True)
            os.makedirs(final_output_dir, exist_ok=True)

            # copy frame into raw_dir for isolated processing
            try:
                dst = os.path.join(raw_dir, os.path.basename(filepath))
                shutil.copyfile(filepath, dst)
            except Exception:
                logging.exception("Failed to copy frame into processing dir")
                dst = filepath

            logging.info(f"Processing frame: {dst}")

            # run pipeline (preprocess -> detect -> extract)
            try:
                preprocess_all(raw_dir=raw_dir, out_dir=preproc_dir)
                run_detection(preprocessed_folder=preproc_dir, output_img_folder=detected_images_dir, output_csv_folder=detected_csvs_dir)
                out_path = os.path.join(final_output_dir, "vision_data.json")
                out_path = run_extraction(csv_dir=detected_csvs_dir, frame_dir=raw_dir, output_json=out_path)

                with open(out_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # push to processed queue
                processed_queue.put({
                    "status": "completed",
                    "vision_data": data,
                    "source_frame": filepath,
                    "processed_at": time.time()
                })
            except Exception as e:
                logging.exception("Per-frame pipeline failed")
                processed_queue.put({"status": "error", "detail": str(e), "source_frame": filepath})

        except Exception:
            logging.exception("Unexpected error in processing_worker")


# -------------------------------
# API Endpoints
# -------------------------------
@app.post("/vision/start")
def start_vision():
    """Start webcam capture (enforce camera_index=0) and create a session folder."""
    global capture_running, capture_thread, current_session

    camera_index = 0  # always use index 0 for the webcam

    if capture_running:
        # already running — return current session id
        return {"status": "already_running", "session_id": current_session.get("id") if current_session else None}

    # create new session
    session_id = f"session_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    session_root = os.path.join(SESSIONS_DIR, session_id)
    raw_dir = os.path.join(session_root, "raw_frames")
    preproc_dir = os.path.join(session_root, "preprocessed_frames")
    detected_images_dir = os.path.join(session_root, "detected_images")
    detected_csvs_dir = os.path.join(session_root, "detected_csvs")
    final_output_dir = os.path.join(session_root, "final_output")

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(preproc_dir, exist_ok=True)
    os.makedirs(detected_images_dir, exist_ok=True)
    os.makedirs(detected_csvs_dir, exist_ok=True)
    os.makedirs(final_output_dir, exist_ok=True)

    current_session = {
        "id": session_id,
        "root": session_root,
        "raw_dir": raw_dir,
        "preproc_dir": preproc_dir,
        "detected_images_dir": detected_images_dir,
        "detected_csvs_dir": detected_csvs_dir,
        "final_output_dir": final_output_dir
    }

    capture_running = True
    capture_thread = threading.Thread(
        target=webcam_capture_loop,
        args=(camera_index, raw_dir),
        daemon=True
    )
    capture_thread.start()

    # start processing worker thread if not already running
    global processing_thread
    if processing_thread is None or not processing_thread.is_alive():
        processing_thread = threading.Thread(target=processing_worker, daemon=True)
        processing_thread.start()

    return {"status": "started", "camera_index": camera_index, "session_id": session_id}


@app.post("/vision/stop")
def stop_vision(session_id: str = None):
    """Stop capture, then run preprocessing -> detection -> extraction for the active session and return final JSON."""
    global capture_running, capture_thread, current_session

    if not capture_running or current_session is None:
        return {"status": "not_running"}

    if session_id and current_session and session_id != current_session.get("id"):
        return {"status": "session_mismatch", "expected": current_session.get("id"), "received": session_id}

    capture_running = False

    # Wait briefly for thread to finish
    if capture_thread and capture_thread.is_alive():
        capture_thread.join(timeout=10)

    raw_dir = current_session.get("raw_dir")
    preproc_dir = current_session.get("preproc_dir")
    detected_csvs_dir = current_session.get("detected_csvs_dir")
    detected_images_dir = current_session.get("detected_images_dir")
    final_output_dir = current_session.get("final_output_dir")

    # Check we have captured frames
    captured_files = [f for f in os.listdir(raw_dir) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
    if not captured_files:
        # reset session so new runs start fresh
        current_session = None
        return {"status": "no_frames_captured"}

    try:
        logging.info("Starting preprocessing...")
        preprocess_all(raw_dir=raw_dir, out_dir=preproc_dir)

        logging.info("Running detection...")
        processed = run_detection(preprocessed_folder=preproc_dir, output_img_folder=detected_images_dir, output_csv_folder=detected_csvs_dir)

        logging.info("Extracting final JSON...")
        out_path = os.path.join(final_output_dir, "vision_data.json")
        out_path = run_extraction(csv_dir=detected_csvs_dir, frame_dir=raw_dir, output_json=out_path)

        # Read and return the JSON content
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # reset session
        current_session = None

        return {"status": "completed", "vision_data": data}

    except Exception as e:
        logging.exception("Vision pipeline failed")
        current_session = None
        return {"status": "error", "detail": str(e)}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW_FRAMES_DIR = os.path.join(BASE_DIR, "data", "raw_frames")

@app.post("/vision/capture")
def capture_once(run_pipeline: bool = False):
    """Save the current frame. If no session is active, run a single-shot pipeline and return JSON.

    - If a session is active and run_pipeline is False: save to session's raw_dir and return saved_frame metadata.
    - If no session is active (single-shot), create a temporary shot session, run preprocess->detect->extract and return the final JSON.
    """
    global latest_frame, latest_result, current_session

    if latest_frame is None:
        return {"status": "no_frame_available"}

    # If inside a session and no explicit run_pipeline requested, just save to that session
    if current_session and not run_pipeline:
        save_dir = current_session.get("raw_dir")
        os.makedirs(save_dir, exist_ok=True)

        filename = f"frame_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
        filepath = os.path.join(save_dir, filename)
        cv2.imwrite(filepath, latest_frame)

        logging.info(f"Frame saved to session: {filepath}")
        response = latest_result.copy()
        response["saved_frame"] = filepath
        return response

    # Single-shot flow (no active session) OR client requested run_pipeline=True
    shot_id = f"shot_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    session_root = os.path.join(SESSIONS_DIR, shot_id)
    raw_dir = os.path.join(session_root, "raw_frames")
    preproc_dir = os.path.join(session_root, "preprocessed_frames")
    detected_images_dir = os.path.join(session_root, "detected_images")
    detected_csvs_dir = os.path.join(session_root, "detected_csvs")
    final_output_dir = os.path.join(session_root, "final_output")

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(preproc_dir, exist_ok=True)
    os.makedirs(detected_images_dir, exist_ok=True)
    os.makedirs(detected_csvs_dir, exist_ok=True)
    os.makedirs(final_output_dir, exist_ok=True)

    # Save the captured frame into the shot raw dir
    filename = f"frame_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
    filepath = os.path.join(raw_dir, filename)
    cv2.imwrite(filepath, latest_frame)
    logging.info(f"Single-shot frame saved: {filepath}")

    try:
        # run preprocessing -> detection -> extraction for this single frame
        logging.info("Starting single-shot preprocessing...")
        preprocess_all(raw_dir=raw_dir, out_dir=preproc_dir)

        logging.info("Running single-shot detection...")
        run_detection(preprocessed_folder=preproc_dir, output_img_folder=detected_images_dir, output_csv_folder=detected_csvs_dir)

        logging.info("Running single-shot extraction...")
        out_path = os.path.join(final_output_dir, "vision_data.json")
        out_path = run_extraction(csv_dir=detected_csvs_dir, frame_dir=raw_dir, output_json=out_path)

        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {"status": "completed", "vision_data": data, "session_id": shot_id}

    except Exception as e:
        logging.exception("Single-shot pipeline failed")
        return {"status": "error", "detail": str(e)}


@app.get("/vision/stream")
def vision_stream():
    """Server-Sent Events endpoint that streams per-frame processed JSON results as they complete.

    Clients should connect with a long-lived GET request and parse `data: ...` SSE messages.
    """
    def event_generator():
        while True:
            try:
                item = processed_queue.get(timeout=30)
                # SSE data: must end with double newline
                yield f"data: {json.dumps(item)}\n\n"
            except Exception:
                # send comment keep-alive to keep connection open
                yield ":\n\n"
                continue

    return StreamingResponse(event_generator(), media_type="text/event-stream")