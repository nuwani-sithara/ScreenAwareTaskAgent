import requests
import logging
import time

VISION_BASE_URL = "http://localhost:8001"  # Vision FastAPI service

def start_capture(timeout=5):
    try:
        r = requests.post(f"{VISION_BASE_URL}/vision/start", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logging.error("Failed to start vision capture: %s", e)
        return None

def stop_and_get_vision(timeout=120):
    """
    Send /vision/stop which stops capture and runs preprocessing->detection->extraction.
    This can take time (model + OCR), so use a generous timeout (e.g. 120s).
    """
    try:
        r = requests.post(f"{VISION_BASE_URL}/vision/stop", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "completed":
            return data.get("vision_data")
        else:
            logging.error("Vision stop returned non-completed status: %s", data.get("status"))
            return {"error": "not_completed", "detail": data}
    except requests.RequestException as e:
        logging.error("Vision stop request failed: %s", e)
        return {"error": "vision_unavailable", "detail": str(e)}

def capture_snapshot(timeout=5):
    """Request a single saved frame (doesn't run full pipeline)."""
    try:
        r = requests.post(f"{VISION_BASE_URL}/vision/capture", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logging.error("Snapshot capture failed: %s", e)
        return {"error": "capture_failed", "detail": str(e)}

def perceive(wait_seconds=3):
    """
    High-level convenience: start capture (if not already), wait `wait_seconds`,
    then stop and fetch the final JSON.
    """
    logging.info("Requesting vision perception (start -> wait -> stop)...")

    start_capture()  # safe to call even if already running

    # allow camera to gather a few frames
    time.sleep(wait_seconds)

    vision_data = stop_and_get_vision(timeout=180)  # increase timeout if dataset/model is large
    if "error" in vision_data:
        logging.error("Perception error: %s", vision_data)
    else:
        logging.info("Perception data received")
    return vision_data