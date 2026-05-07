from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import threading
import time
import logging
import cv2
import os
import uuid
import queue
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

import mss
import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Force screenshot mode for Vision 2.0 unless explicitly overridden.
os.environ.setdefault("VISION_SCREENSHOT_MODE", "1")

from src.api import _new_session, _run_pipeline_for_frame, _init_semantic_pipeline, _init_vlm_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Vision 2.0 Service")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SESSIONS_DIR = os.path.join(BASE_DIR, "data", "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

capture_running = False
capture_thread = None
processing_thread = None
latest_frame = None
latest_result: Dict[str, Any] = {}
current_session: Optional[Dict[str, Any]] = None

processing_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
processed_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
session_lock = threading.Lock()
processing_inflight: Dict[str, int] = {}
sessions_by_id: Dict[str, Dict[str, Any]] = {}


def _capture_screenshot(monitor_index: int = 1):
    with mss.mss() as sct:
        monitors = sct.monitors
        if not monitors:
            return None
        if monitor_index < 0 or monitor_index >= len(monitors):
            monitor_index = 1 if len(monitors) > 1 else 0
        monitor = monitors[monitor_index]
        img = np.array(sct.grab(monitor))
        if img is None or img.size == 0:
            return None
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def _process_single_frame_item(
    session: Dict[str, Any],
    session_id: str,
    frame_path: str,
) -> Dict[str, Any]:
    logger.info("Processing frame session_id=%s frame=%s", session_id, Path(frame_path).name)
    result = _run_pipeline_for_frame(
        frame_path=frame_path,
        session=session,
        vlm_client=session.get("vlm_client"),
        semantic_pipeline=session.get("semantic_pipeline"),
        coarse_max_boxes=int(session.get("coarse_max_boxes", 180)),
        refined_max_elements=int(session.get("refined_max_elements", 120)),
        vlm_batch_max_elements=int(session.get("vlm_batch_max_elements", 90)),
    )

    agg = session.get("aggregator")
    if agg is not None and agg.is_active:
        try:
            agg.append_frame(frame_path, result)
            logger.debug("Appended frame result to session aggregator session_id=%s", session_id)
        except Exception as _agg_exc:
            logger.warning("SessionAggregator.append_frame failed: %s", _agg_exc)

    processed_queue.put(result)
    return result


def _pull_next_queued_item_for_session(session_id: str) -> Optional[Dict[str, Any]]:
    deferred: List[Dict[str, Any]] = []
    target: Optional[Dict[str, Any]] = None

    while True:
        try:
            item = processing_queue.get_nowait()
        except queue.Empty:
            break
        if target is None and item.get("session_id") == session_id:
            target = item
            break
        deferred.append(item)

    for item in deferred:
        processing_queue.put(item)

    return target


def screenshot_capture_loop(monitor_index: int, save_dir: str, save_interval: float = 1.0):
    """Capture loop for desktop screenshots. Enqueues frame paths for processing."""
    global capture_running, latest_frame, latest_result

    logger.info(
        "Screenshot capture loop started monitor_index=%s save_dir=%s interval=%.2f",
        monitor_index,
        save_dir,
        save_interval,
    )
    os.makedirs(save_dir, exist_ok=True)

    last_saved = 0.0
    last_saved_small = None

    try:
        while capture_running:
            frame = _capture_screenshot(monitor_index=monitor_index)
            if frame is None:
                time.sleep(0.1)
                continue

            latest_frame = frame
            latest_result = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "frame": {"width": frame.shape[1], "height": frame.shape[0]},
                "status": "frame_captured",
            }

            now = time.time()
            save_flag = False

            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                h, w = gray.shape[:2]
                max_dim = 320
                scale = max_dim / max(h, w) if max(h, w) > max_dim else 1.0
                small = cv2.resize(gray, (int(w * scale), int(h * scale))) if scale != 1.0 else gray
                if last_saved_small is None:
                    save_flag = True
                else:
                    diff = cv2.absdiff(small, last_saved_small)
                    _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                    ratio = int(cv2.countNonZero(thresh)) / float(thresh.size)
                    save_flag = True
                    logger.debug("Frame change ratio=%.4f session_id=%s", ratio, current_session["id"] if current_session else None)
            except Exception:
                save_flag = True
                small = None

            if now - last_saved >= save_interval and save_flag:
                filename = f"frame_{int(now)}_{uuid.uuid4().hex[:6]}.jpg"
                frame_path = os.path.join(save_dir, filename)
                cv2.imwrite(frame_path, frame)

                with session_lock:
                    sid = current_session["id"] if current_session else None
                if sid:
                    processing_queue.put({"session_id": sid, "frame_path": frame_path})
                    logger.debug("Enqueued frame for processing session_id=%s frame=%s", sid, filename)

                last_saved = now
                if small is not None:
                    last_saved_small = small.copy()

            time.sleep(0.05)

    except Exception as e:
        logger.exception("Screenshot capture error: %s", e)

    logger.info("Screenshot capture loop stopped")


def processing_worker():
    """Background worker that processes enqueued frames."""
    global current_session, processing_inflight
    logger.info("Processing worker started")

    while True:
        try:
            item = processing_queue.get(timeout=1.0)
        except Exception:
            time.sleep(0.1)
            continue

        session_id = item.get("session_id")
        frame_path = item.get("frame_path")
        if not session_id or not frame_path:
            continue

        try:
            with session_lock:
                processing_inflight[session_id] = processing_inflight.get(session_id, 0) + 1

            with session_lock:
                session = sessions_by_id.get(session_id)

            if not session:
                logger.warning("Dropping frame for unknown session_id=%s", session_id)
                continue

            _process_single_frame_item(session, session_id, frame_path)

        except Exception:
            logger.exception("Per-frame pipeline failed")
            processed_queue.put(
                {
                    "status": "error",
                    "session_id": session_id,
                    "source_frame": frame_path,
                    "processed_at": time.time(),
                    "detail": "processing_failed",
                }
            )
        finally:
            with session_lock:
                if session_id in processing_inflight:
                    processing_inflight[session_id] = max(0, processing_inflight[session_id] - 1)
                    if processing_inflight[session_id] == 0:
                        del processing_inflight[session_id]


@app.post("/vision/start")
def start_vision(
    monitor_index: int = 1,
    camera_index: int = 0,
    save_interval: float = 1.0,
    coarse_max_boxes: int = 180,
    refined_max_elements: int = 120,
    vlm_batch_max_elements: int = 90,
    no_vlm: bool = False,
):
    """Start continuous desktop screenshot capture + processing session."""
    global capture_running, capture_thread, processing_thread, current_session

    effective_monitor = monitor_index if monitor_index is not None else camera_index
    logger.info(
        "Received /vision/start monitor_index=%s save_interval=%.2f no_vlm=%s",
        effective_monitor,
        save_interval,
        no_vlm,
    )

    with session_lock:
        if capture_running and current_session:
            logger.info("Vision 2.0 session already running session_id=%s", current_session.get("id"))
            return {
                "status": "already_running",
                "session_id": current_session.get("id"),
            }

    try:
        vlm_client = _init_vlm_client(no_vlm=no_vlm)
        semantic_pipeline = _init_semantic_pipeline(no_vlm=no_vlm)
    except Exception as e:
        logger.exception("VLM init failed")
        return {"status": "error", "detail": f"VLM init failed: {e}"}

    session = _new_session(prefix="session", aggregate=True)
    session.update(
        {
            "monitor_index": effective_monitor,
            "save_interval": save_interval,
            "coarse_max_boxes": coarse_max_boxes,
            "refined_max_elements": refined_max_elements,
            "vlm_batch_max_elements": vlm_batch_max_elements,
            "no_vlm": no_vlm,
            "vlm_client": vlm_client,
            "semantic_pipeline": semantic_pipeline,
        }
    )

    with session_lock:
        current_session = session
        capture_running = True
        sessions_by_id[session["id"]] = session
    logger.info("Vision 2.0 session started session_id=%s root=%s", session["id"], session["root"])

    capture_thread = threading.Thread(
        target=screenshot_capture_loop,
        args=(effective_monitor, session["raw_dir"], save_interval),
        daemon=True,
    )
    capture_thread.start()

    if processing_thread is None or not processing_thread.is_alive():
        processing_thread = threading.Thread(target=processing_worker, daemon=True)
        processing_thread.start()

    return {
        "status": "started",
        "session_id": session["id"],
        "monitor_index": effective_monitor,
        "save_interval": save_interval,
        "coarse_max_boxes": coarse_max_boxes,
        "refined_max_elements": refined_max_elements,
        "vlm_batch_max_elements": vlm_batch_max_elements,
        "no_vlm": no_vlm,
        "session_root": session["root"],
    }


@app.post("/vision/stop")
def stop_vision(
    session_id: Optional[str] = None,
    wait_for_processing: bool = True,
    processing_timeout: float = 30.0,
):
    """Stop continuous screenshot capture session."""
    global capture_running, capture_thread, current_session

    logger.info(
        "Received /vision/stop session_id=%s wait_for_processing=%s timeout=%.1f",
        session_id,
        wait_for_processing,
        processing_timeout,
    )

    with session_lock:
        if not capture_running or current_session is None:
            logger.info("Stop requested but no active session is running")
            return {"status": "not_running"}

        if session_id and current_session.get("id") != session_id:
            logger.warning(
                "Stop session mismatch expected=%s received=%s",
                current_session.get("id"),
                session_id,
            )
            return {
                "status": "session_mismatch",
                "expected": current_session.get("id"),
                "received": session_id,
            }

        session = current_session
        capture_running = False

    if capture_thread and capture_thread.is_alive():
        logger.info("Waiting for capture thread to stop")
        capture_thread.join(timeout=10)

    if wait_for_processing:
        deadline = time.time() + max(0.0, processing_timeout)
        logger.info("Waiting for processing queue to drain until %.1f seconds from now", processing_timeout)
        while time.time() < deadline:
            with session_lock:
                inflight = processing_inflight.get(session["id"], 0)
            with processing_queue.mutex:
                queued_for_session = sum(
                    1 for item in list(processing_queue.queue)
                    if item.get("session_id") == session["id"]
                )
            if inflight == 0 and queued_for_session == 0:
                break
            time.sleep(0.1)

        while True:
            with session_lock:
                inflight = processing_inflight.get(session["id"], 0)
            item = _pull_next_queued_item_for_session(session["id"])

            if item is None:
                if inflight == 0:
                    break
                time.sleep(0.1)
                continue

            frame_path = item.get("frame_path")
            if not frame_path:
                continue
            try:
                _process_single_frame_item(session, session["id"], frame_path)
            except Exception as exc:
                logger.exception("Synchronous drain processing failed: %s", exc)

    session_summary_path: Optional[str] = None
    session_doc: Optional[Dict[str, Any]] = None
    agg = session.get("aggregator")
    if agg is not None and agg.is_active:
        try:
            session_doc = agg.finalize(save=True)
            session_summary_path = str(
                Path(session["root"]) / f"{agg.session_id}_summary.json"
            )
            logger.info(
                "Session summary saved: %s  screens=%d",
                session_summary_path, session_doc.get("screen_count", 0),
            )
        except Exception as _fin_exc:
            logger.warning("SessionAggregator.finalize failed: %s", _fin_exc)

    summary = {
        "status": "stopped",
        "session_id": session["id"],
        "session_root": session["root"],
        "session_summary_path": session_summary_path,
        "raw_frames": len(list(Path(session["raw_dir"]).glob("*.jpg"))),
        "preprocessed_frames": len(list(Path(session["preproc_dir"]).glob("*.jpg"))),
        "final_json": len(list(Path(session["final_dir"]).glob("*.json"))),
        "session_data": session_doc,
    }

    with session_lock:
        current_session = None
        sessions_by_id.pop(session["id"], None)

    logger.info("Vision 2.0 session stopped session_id=%s", session["id"])

    return summary


@app.post("/vision/capture")
def capture_once(
    monitor_index: int = 1,
    camera_index: int = 0,
    coarse_max_boxes: int = 180,
    refined_max_elements: int = 120,
    vlm_batch_max_elements: int = 90,
    no_vlm: bool = False,
    use_current_session: bool = False,
    provider: str = "openai",
):
    """Single-shot desktop screenshot capture and pipeline execution."""
    effective_monitor = monitor_index if monitor_index is not None else camera_index

    if use_current_session:
        with session_lock:
            active_session = current_session if capture_running and current_session else None
        if active_session is not None:
            frame = _capture_screenshot(monitor_index=effective_monitor)
            if frame is None:
                return {
                    "status": "error",
                    "detail": "Failed to capture screenshot from active session.",
                    "session_id": active_session.get("id"),
                }
            frame_name = f"instant_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
            frame_path = os.path.join(active_session["raw_dir"], frame_name)
            cv2.imwrite(frame_path, frame)
            try:
                result = _process_single_frame_item(active_session, active_session["id"], frame_path)
                result["capture_mode"] = "instant_stream"
                return result
            except Exception as e:
                logger.exception("Instant stream capture failed")
                return {
                    "status": "error",
                    "session_id": active_session.get("id"),
                    "detail": str(e),
                }

    frame = _capture_screenshot(monitor_index=effective_monitor)
    if frame is None:
        return {"status": "error", "detail": "Failed to capture screenshot"}

    with session_lock:
        _reuse_session = current_session if capture_running and current_session else None

    if _reuse_session is not None and not no_vlm:
        vlm_client = _reuse_session.get("vlm_client")
        semantic_pipeline = _reuse_session.get("semantic_pipeline")
    else:
        try:
            vlm_client = _init_vlm_client(no_vlm=no_vlm)
            semantic_pipeline = _init_semantic_pipeline(no_vlm=no_vlm)
        except Exception as e:
            return {"status": "error", "detail": f"VLM init failed: {e}"}

    session = _new_session(prefix="shot")
    session.update(
        {
            "coarse_max_boxes": coarse_max_boxes,
            "refined_max_elements": refined_max_elements,
            "vlm_batch_max_elements": vlm_batch_max_elements,
        }
    )
    with session_lock:
        sessions_by_id[session["id"]] = session

    frame_name = f"frame_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
    frame_path = os.path.join(session["raw_dir"], frame_name)
    cv2.imwrite(frame_path, frame)

    try:
        result = _run_pipeline_for_frame(
            frame_path=frame_path,
            session=session,
            vlm_client=vlm_client,
            semantic_pipeline=semantic_pipeline,
            coarse_max_boxes=coarse_max_boxes,
            refined_max_elements=refined_max_elements,
            vlm_batch_max_elements=vlm_batch_max_elements,
        )
        return result
    except Exception as e:
        logger.exception("Single-shot pipeline failed")
        return {
            "status": "error",
            "session_id": session["id"],
            "detail": str(e),
        }
    finally:
        with session_lock:
            sessions_by_id.pop(session["id"], None)


@app.get("/vision/stream")
def vision_stream(session_id: Optional[str] = None):
    """
    SSE endpoint for processed frame JSON items.
    - If session_id is provided, only emits events for that session.
    """

    def event_generator():
        while True:
            try:
                item = processed_queue.get(timeout=30)
                if session_id and item.get("session_id") != session_id:
                    continue
                yield f"data: {json.dumps(item)}\n\n"
            except Exception:
                yield ":\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/vision/status")
def vision_status():
    with session_lock:
        running = capture_running
        session = current_session

    return {
        "running": running,
        "session_id": session.get("id") if session else None,
        "latest_result": latest_result,
    }
