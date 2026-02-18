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
import json
from pathlib import Path
from typing import Optional, Dict, Any

from src.capture.webcam_capture import start_webcam_stream
from src.preprocessing.preprocess import preprocess_all
from src.perception.grounding.coarse_bbox_generator import generate_coarse_bboxes
from src.perception.grounding.bbox_refiner import BBoxRefiner
from src.perception.grounding.bbox_element_enricher import enrich_frame
from src.perception.vlm import get_vlm_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="Vision Service")

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


def _new_session(prefix: str = "session") -> Dict[str, Any]:
    session_id = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    root = os.path.join(SESSIONS_DIR, session_id)

    raw_dir = os.path.join(root, "raw_frames")
    preproc_dir = os.path.join(root, "preprocessed_frames")
    coarse_dir = os.path.join(root, "coarse_bboxes")
    refined_dir = os.path.join(root, "refined_bboxes")
    refined_debug_dir = os.path.join(refined_dir, "debug")
    final_dir = os.path.join(root, "final_elements")
    proc_dir = os.path.join(root, "processing")

    for d in [raw_dir, preproc_dir, coarse_dir, refined_dir, refined_debug_dir, final_dir, proc_dir]:
        os.makedirs(d, exist_ok=True)

    return {
        "id": session_id,
        "root": root,
        "raw_dir": raw_dir,
        "preproc_dir": preproc_dir,
        "coarse_dir": coarse_dir,
        "refined_dir": refined_dir,
        "refined_debug_dir": refined_debug_dir,
        "final_dir": final_dir,
        "proc_dir": proc_dir,
        "created_at": time.time(),
    }


def _init_vlm_client(provider: str, local_model: str, no_vlm: bool, ollama_base_url: Optional[str] = None):
    if no_vlm:
        return None
    kwargs = {"model_name": local_model} if provider in {"local", "ollama"} else {}
    if provider == "ollama" and ollama_base_url:
        kwargs["base_url"] = ollama_base_url
    return get_vlm_client(provider, **kwargs)


def _write_refined_debug_image(image, refined_bboxes, out_path: str) -> None:
    vis = image.copy()
    h, w = vis.shape[:2]
    for item in refined_bboxes:
        x1, y1, x2, y2 = item["bbox"]
        cv2.rectangle(
            vis,
            (int(x1 * w), int(y1 * h)),
            (int(x2 * w), int(y2 * h)),
            (0, 255, 0),
            2,
        )
    cv2.imwrite(out_path, vis)


def _capture_single_frame(camera_index: int = 0):
    backend = cv2.CAP_DSHOW if os.name == "nt" else 0
    cap = cv2.VideoCapture(camera_index, backend)
    if not cap.isOpened():
        return None
    frame = None
    try:
        for _ in range(5):
            ok, f = cap.read()
            if ok:
                frame = f
            time.sleep(0.03)
    finally:
        cap.release()
    return frame


def _run_pipeline_for_frame(frame_path: str, session: Dict[str, Any], vlm_client=None) -> Dict[str, Any]:
    """
    Run: preprocess -> coarse bbox -> refine bbox -> enrich elements.
    Stores artifacts under session folders and returns final JSON payload.
    """
    frame_name = Path(frame_path).name
    frame_stem = Path(frame_path).stem

    proc_root = os.path.join(session["proc_dir"], f"proc_{int(time.time())}_{uuid.uuid4().hex[:6]}")
    proc_raw = os.path.join(proc_root, "raw_frames")
    proc_pre = os.path.join(proc_root, "preprocessed_frames")
    os.makedirs(proc_raw, exist_ok=True)
    os.makedirs(proc_pre, exist_ok=True)

    isolated_raw = os.path.join(proc_raw, frame_name)
    shutil.copyfile(frame_path, isolated_raw)

    preprocess_all(raw_dir=proc_raw, out_dir=proc_pre)
    preprocessed_image = os.path.join(proc_pre, frame_name)

    # Persist preprocessed image in session folder
    session_preprocessed = os.path.join(session["preproc_dir"], frame_name)
    shutil.copyfile(preprocessed_image, session_preprocessed)

    image = cv2.imread(preprocessed_image)
    if image is None:
        raise RuntimeError(f"Failed to read preprocessed frame: {preprocessed_image}")

    # Coarse bboxes
    coarse_bboxes = generate_coarse_bboxes(image)
    coarse_json_path = os.path.join(session["coarse_dir"], f"{frame_stem}.json")
    with open(coarse_json_path, "w", encoding="utf-8") as f:
        json.dump({"bboxes": coarse_bboxes}, f, indent=2)

    # Refine bboxes
    refiner = BBoxRefiner()
    refined_bboxes = []
    for item in coarse_bboxes:
        refined = refiner.refine_bbox(
            image=image,
            bbox_normalized=tuple(item["bbox"]),
            use_edge_detection=True,
            use_grid_snap=False,
        )
        if refiner.validate_bbox(refined):
            refined_bboxes.append(
                {
                    "bbox": list(refined),
                    "source": item.get("source", "layout"),
                    "confidence": item.get("confidence", 0.5),
                }
            )

    refined_json_path = os.path.join(session["refined_dir"], f"{frame_stem}.json")
    with open(refined_json_path, "w", encoding="utf-8") as f:
        json.dump({"bboxes": refined_bboxes}, f, indent=2)
    debug_image_path = os.path.join(session["refined_debug_dir"], frame_name)
    _write_refined_debug_image(image, refined_bboxes, debug_image_path)

    # Enrich with element metadata (local VLM or fallback no-vlm)
    final_json_path = os.path.join(session["final_dir"], f"{frame_stem}.json")
    enrich_frame(
        image_path=Path(session_preprocessed),
        refined_bbox_path=Path(refined_json_path),
        out_path=Path(final_json_path),
        vlm_client=vlm_client,
    )

    with open(final_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    return {
        "status": "completed",
        "session_id": session["id"],
        "source_frame": frame_path,
        "processed_at": time.time(),
        "final_json_path": final_json_path,
        "vision_data": payload,
    }


def webcam_capture_loop(camera_index: int, save_dir: str, save_interval: float = 1.0):
    """Capture loop with basic change detection. Enqueues frame paths for processing."""
    global capture_running, latest_frame, latest_result

    logging.info("Webcam capture loop started")
    os.makedirs(save_dir, exist_ok=True)

    last_saved = 0.0
    last_saved_small = None
    change_threshold = 0.01

    try:
        stream = start_webcam_stream(camera_index)
        for frame in stream:
            if not capture_running:
                break

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
                    if ratio >= change_threshold:
                        save_flag = True
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

                last_saved = now
                if small is not None:
                    last_saved_small = small.copy()

            time.sleep(0.05)

    except Exception as e:
        logging.error(f"Webcam error: {e}")

    logging.info("Webcam capture loop stopped")


def processing_worker():
    """Background worker that processes enqueued frames."""
    global current_session
    logging.info("Processing worker started")

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
                session = current_session if current_session and current_session.get("id") == session_id else None

            if not session:
                continue

            result = _run_pipeline_for_frame(
                frame_path=frame_path,
                session=session,
                vlm_client=session.get("vlm_client"),
            )
            processed_queue.put(result)

        except Exception as e:
            logging.exception("Per-frame pipeline failed")
            processed_queue.put(
                {
                    "status": "error",
                    "session_id": session_id,
                    "source_frame": frame_path,
                    "processed_at": time.time(),
                    "detail": str(e),
                }
            )


@app.post("/vision/start")
def start_vision(
    camera_index: int = 0,
    save_interval: float = 1.0,
    provider: str = "local",
    local_model: str = "llava-hf/llava-1.5-7b-hf",
    ollama_base_url: Optional[str] = None,
    no_vlm: bool = False,
):
    """Start continuous capture + processing session."""
    global capture_running, capture_thread, processing_thread, current_session

    with session_lock:
        if capture_running and current_session:
            return {
                "status": "already_running",
                "session_id": current_session.get("id"),
            }

    try:
        vlm_client = _init_vlm_client(
            provider=provider,
            local_model=local_model,
            no_vlm=no_vlm,
            ollama_base_url=ollama_base_url,
        )
    except Exception as e:
        return {"status": "error", "detail": f"VLM init failed: {e}"}

    session = _new_session(prefix="session")
    session.update(
        {
            "camera_index": camera_index,
            "save_interval": save_interval,
            "provider": provider,
            "local_model": local_model,
            "ollama_base_url": ollama_base_url,
            "no_vlm": no_vlm,
            "vlm_client": vlm_client,
        }
    )

    with session_lock:
        current_session = session
        capture_running = True

    capture_thread = threading.Thread(
        target=webcam_capture_loop,
        args=(camera_index, session["raw_dir"], save_interval),
        daemon=True,
    )
    capture_thread.start()

    if processing_thread is None or not processing_thread.is_alive():
        processing_thread = threading.Thread(target=processing_worker, daemon=True)
        processing_thread.start()

    return {
        "status": "started",
        "session_id": session["id"],
        "camera_index": camera_index,
        "save_interval": save_interval,
        "provider": provider,
        "local_model": local_model,
        "ollama_base_url": ollama_base_url,
        "no_vlm": no_vlm,
        "session_root": session["root"],
    }


@app.post("/vision/stop")
def stop_vision(session_id: Optional[str] = None):
    """Stop continuous capture session."""
    global capture_running, capture_thread, current_session

    with session_lock:
        if not capture_running or current_session is None:
            return {"status": "not_running"}

        if session_id and current_session.get("id") != session_id:
            return {
                "status": "session_mismatch",
                "expected": current_session.get("id"),
                "received": session_id,
            }

        session = current_session
        capture_running = False

    if capture_thread and capture_thread.is_alive():
        capture_thread.join(timeout=10)

    summary = {
        "status": "stopped",
        "session_id": session["id"],
        "session_root": session["root"],
        "raw_frames": len(list(Path(session["raw_dir"]).glob("*.jpg"))),
        "preprocessed_frames": len(list(Path(session["preproc_dir"]).glob("*.jpg"))),
        "coarse_json": len(list(Path(session["coarse_dir"]).glob("*.json"))),
        "refined_json": len(list(Path(session["refined_dir"]).glob("*.json"))),
        "refined_debug_images": len(list(Path(session["refined_debug_dir"]).glob("*.jpg"))),
        "final_json": len(list(Path(session["final_dir"]).glob("*.json"))),
    }

    with session_lock:
        current_session = None

    return summary


@app.post("/vision/capture")
def capture_once(
    camera_index: int = 0,
    provider: str = "local",
    local_model: str = "llava-hf/llava-1.5-7b-hf",
    ollama_base_url: Optional[str] = None,
    no_vlm: bool = False,
):
    """Single-shot capture and pipeline execution. Returns final JSON."""
    frame = _capture_single_frame(camera_index=camera_index)
    if frame is None:
        return {"status": "error", "detail": f"Failed to capture frame from camera {camera_index}"}

    try:
        vlm_client = _init_vlm_client(
            provider=provider,
            local_model=local_model,
            no_vlm=no_vlm,
            ollama_base_url=ollama_base_url,
        )
    except Exception as e:
        return {"status": "error", "detail": f"VLM init failed: {e}"}

    session = _new_session(prefix="shot")
    frame_name = f"frame_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
    frame_path = os.path.join(session["raw_dir"], frame_name)
    cv2.imwrite(frame_path, frame)

    try:
        result = _run_pipeline_for_frame(frame_path=frame_path, session=session, vlm_client=vlm_client)
        return result
    except Exception as e:
        logging.exception("Single-shot pipeline failed")
        return {
            "status": "error",
            "session_id": session["id"],
            "detail": str(e),
        }


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
        "camera_index": session.get("camera_index") if session else None,
        "provider": session.get("provider") if session else None,
        "no_vlm": session.get("no_vlm") if session else None,
    }
