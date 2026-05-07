import requests
import logging
import time
import json
import os

VISION_MODE = os.getenv("VISION_MODE", "vision").strip().lower()
VISION_BASE_URL = os.getenv("VISION_BASE_URL", "http://localhost:8001")
VISION2_BASE_URL = os.getenv("VISION2_BASE_URL", "http://localhost:8003")
if VISION_MODE in {"vision2", "vision_2", "v2"}:
    VISION_BASE_URL = VISION2_BASE_URL

def start_capture(timeout=5):
    try:
        r = requests.post(f"{VISION_BASE_URL}/vision/start", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logging.error("Failed to start vision capture: %s", e)
        return None

def stop_and_get_vision(session_id=None, timeout=120):
    """
    Send /vision/stop which stops capture and runs preprocessing->detection->extraction.
    This can take time (model + OCR), so use a generous timeout (e.g. 120s).
    Optionally pass the session_id as a query parameter to ensure we stop the correct session.
    """
    try:
        params = {"session_id": session_id} if session_id else {}
        r = requests.post(f"{VISION_BASE_URL}/vision/stop", params=params, timeout=timeout)
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

def capture_snapshot(timeout=180, run_pipeline=True):
    """
    Request a single saved frame and run full pipeline on it. Returns the parsed vision JSON on success.

    By default this runs the full pipeline (run_pipeline=True) and uses a generous timeout.
    """
    try:
        params = {"run_pipeline": "true"} if run_pipeline else {}
        r = requests.post(f"{VISION_BASE_URL}/vision/capture", params=params, timeout=timeout)
        r.raise_for_status()
        resp = r.json()

        # If pipeline completed, return the vision data
        if isinstance(resp, dict) and resp.get("status") == "completed" and "vision_data" in resp:
            return resp.get("vision_data")

        # If it's only a saved frame metadata, return it
        if isinstance(resp, dict) and "saved_frame" in resp:
            return resp

        return resp

    except requests.RequestException as e:
        logging.error("Snapshot capture failed: %s", e)
        return {"error": "capture_failed", "detail": str(e)}


def stream_vision(connect_timeout=5, max_events=None):
    """Connect to the Vision SSE stream and yield parsed JSON events as they arrive.

    Usage:
        for item in stream_vision():
            handle(item)
    """
    url = f"{VISION_BASE_URL}/vision/stream"
    try:
        with requests.get(url, stream=True, timeout=connect_timeout) as resp:
            resp.raise_for_status()
            event_count = 0
            buffer = ""
            for raw_line in resp.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue
                line = raw_line.strip()
                # SSE keep-alive comment
                if line == "":
                    # end of event, parse buffer if contains data
                    if buffer.startswith("data:"):
                        payload = buffer[len("data:"):].strip()
                        try:
                            data = json.loads(payload)
                        except Exception:
                            data = {"error": "invalid_json", "raw": payload}
                        yield data
                        event_count += 1
                        if max_events and event_count >= max_events:
                            break
                    buffer = ""
                    continue

                # accumulate 'data:' lines (SSE may send multiple lines)
                if line.startswith("data:"):
                    buffer += line + "\n"
                # ignore other SSE fields (id:, retry:, :)

    except requests.RequestException as e:
        logging.error("Failed to connect to vision stream: %s", e)
        yield {"error": "stream_unavailable", "detail": str(e)}


def start_and_stream(max_events=None, process_callback=None, connect_timeout=5):
    """Convenience: start capture, then stream processed frames and optionally call a callback per event.

    Returns a list of collected events if `process_callback` is None.
    """
    start_resp = start_capture()
    session_id = None
    if start_resp and isinstance(start_resp, dict):
        session_id = start_resp.get("session_id")

    collected = []
    for item in stream_vision(connect_timeout=connect_timeout, max_events=max_events):
        if process_callback:
            try:
                process_callback(item)
            except Exception:
                logging.exception("process_callback failed")
        else:
            collected.append(item)

        # if the item contains an instruction to stop vision, break
        try:
            if isinstance(item, dict) and item.get("vision_data"):
                # the pipeline result may contain a semantic_state with stop instructions
                pass
        except Exception:
            pass

    return collected

def perceive(wait_seconds=3):
    """
    High-level convenience: start capture (if not already), wait `wait_seconds`,
    then stop and fetch the final JSON.
    """
    logging.info("Requesting vision perception (start -> wait -> stop)...")

    start_resp = start_capture()
    session_id = None
    if start_resp and isinstance(start_resp, dict):
        session_id = start_resp.get("session_id")

    # allow camera to gather a few frames
    time.sleep(wait_seconds)

    vision_data = stop_and_get_vision(session_id=session_id, timeout=180)  # increase timeout if dataset/model is large
    if isinstance(vision_data, dict) and vision_data.get("error"):
        logging.error("Perception error: %s", vision_data)
    else:
        logging.info("Perception data received")
    return vision_data