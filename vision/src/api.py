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
from typing import Optional, Dict, Any, List, Tuple

from src.capture.webcam_capture import start_webcam_stream
from src.preprocessing.preprocess import preprocess_all
from src.perception.grounding.coarse_bbox_generator import generate_coarse_bboxes
from src.perception.grounding.bbox_refiner import BBoxRefiner
from src.perception.grounding.bbox_element_enricher import enrich_frame
from src.perception.vlm import get_vlm_client, UIElement
from src.session_aggregator import SessionAggregator

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
processing_inflight: Dict[str, int] = {}
sessions_by_id: Dict[str, Dict[str, Any]] = {}


def _new_session(prefix: str = "session", aggregate: bool = False) -> Dict[str, Any]:
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

    session: Dict[str, Any] = {
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
        "aggregator": None,
    }
    if aggregate:
        agg = SessionAggregator(
            output_dir=root,
            detect_deltas=True,
            dedup_frames=True,
        )
        agg.start(session_id=session_id)
        session["aggregator"] = agg
    return session


def _init_vlm_client(provider: str, local_model: str, no_vlm: bool, ollama_base_url: Optional[str] = None):
    if no_vlm:
        return None
    kwargs = {"model_name": local_model} if provider in {"local", "ollama"} else {}
    if provider == "ollama" and ollama_base_url:
        kwargs["base_url"] = ollama_base_url
    return get_vlm_client(provider, **kwargs)


def _bbox_iou_norm(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    x1, y1 = max(ax1, bx1), max(ay1, by1)
    x2, y2 = min(ax2, bx2), min(ay2, by2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    a_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = a_area + b_area - inter
    return inter / denom if denom > 0 else 0.0


def _bbox_contained_ratio_norm(inner: Tuple[float, float, float, float], outer: Tuple[float, float, float, float]) -> float:
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    x1, y1 = max(ix1, ox1), max(iy1, oy1)
    x2, y2 = min(ix2, ox2), min(iy2, oy2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    inner_area = max(1e-9, (ix2 - ix1) * (iy2 - iy1))
    return inter / inner_area


def _dedupe_and_rank_refined_bboxes(
    boxes: List[Dict[str, Any]],
    max_elements: int,
) -> List[Dict[str, Any]]:
    if not boxes:
        return []

    source_weight = {
        "layout_form": 1.00,
        "layout_text": 0.95,
        "layout_adaptive": 0.85,
        "layout_edge": 0.75,
        "layout": 0.70,
    }

    def _score(item: Dict[str, Any]) -> float:
        bbox = item.get("bbox", [0, 0, 1, 1])
        x1, y1, x2, y2 = bbox
        area = max(1e-9, (x2 - x1) * (y2 - y1))
        conf = float(item.get("confidence", 0.5))
        sw = source_weight.get(str(item.get("source", "layout")), 0.65)
        return (0.65 * conf) + (0.35 * sw) - (0.05 * area)

    ranked = sorted(boxes, key=_score, reverse=True)
    kept: List[Dict[str, Any]] = []

    for candidate in ranked:
        cb = tuple(candidate.get("bbox", [0, 0, 1, 1]))
        c_source = str(candidate.get("source", "layout"))
        skip = False
        for existing in kept:
            eb = tuple(existing.get("bbox", [0, 0, 1, 1]))
            iou = _bbox_iou_norm(cb, eb)
            contained = _bbox_contained_ratio_norm(cb, eb)
            if iou >= 0.82:
                skip = True
                break
            if contained >= 0.97 and c_source not in {"layout_text", "layout_form"}:
                skip = True
                break
        if not skip:
            kept.append(candidate)
        if len(kept) >= max_elements:
            break

    return kept


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


def _capture_single_frame(camera_index: int = 1):
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


def _process_single_frame_item(
    session: Dict[str, Any],
    session_id: str,
    frame_path: str,
) -> Dict[str, Any]:
    result = _run_pipeline_for_frame(
        frame_path=frame_path,
        session=session,
        vlm_client=session.get("vlm_client"),
        ollama_timeout_seconds=session.get("ollama_timeout_seconds"),
        coarse_max_boxes=int(session.get("coarse_max_boxes", 180)),
        refined_max_elements=int(session.get("refined_max_elements", 120)),
        vlm_batch_max_elements=int(session.get("vlm_batch_max_elements", 90)),
    )

    agg = session.get("aggregator")
    if agg is not None and agg.is_active:
        try:
            agg.append_frame(frame_path, result)
        except Exception as _agg_exc:
            logging.warning("SessionAggregator.append_frame failed: %s", _agg_exc)

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


def _run_pipeline_for_frame(
    frame_path: str,
    session: Dict[str, Any],
    vlm_client=None,
    ollama_timeout_seconds: Optional[float] = None,
    coarse_max_boxes: int = 180,
    refined_max_elements: int = 120,
    vlm_batch_max_elements: int = 90,
) -> Dict[str, Any]:
    """
    Run full pipeline for one frame:
      preprocess → coarse bbox → refine bbox → enrich (layout/fallback) →
      VLM single-call batch classification → save final JSON.

    VLM classification uses ``classify_elements_batch()`` which issues ONE
    call per frame regardless of element count, eliminating the per-element
    budget problem.
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
    coarse_bboxes = generate_coarse_bboxes(image, max_boxes=max(20, int(coarse_max_boxes)))
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

    refined_bboxes = _dedupe_and_rank_refined_bboxes(
        refined_bboxes,
        max_elements=max(20, int(refined_max_elements)),
    )

    refined_json_path = os.path.join(session["refined_dir"], f"{frame_stem}.json")
    with open(refined_json_path, "w", encoding="utf-8") as f:
        json.dump({"bboxes": refined_bboxes}, f, indent=2)
    debug_image_path = os.path.join(session["refined_debug_dir"], frame_name)
    _write_refined_debug_image(image, refined_bboxes, debug_image_path)

    # Enrich elements using layout heuristics only (no per-element VLM calls).
    # VLM classification is done below in a single batch call.
    final_json_path = os.path.join(session["final_dir"], f"{frame_stem}.json")
    enrich_frame(
        image_path=Path(session_preprocessed),
        refined_bbox_path=Path(refined_json_path),
        out_path=Path(final_json_path),
        vlm_client=None,          # disable per-element VLM inside enrich_frame
        ollama_call_budget=0,
        ollama_timeout_seconds=ollama_timeout_seconds,
    )

    # Single-call batch VLM classification (ISSUE 1 fix).
    # Converts all "unknown" / low-confidence elements in ONE model call.
    if vlm_client is not None:
        with open(final_json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        raw_elements = payload.get("elements", [])
        if raw_elements:
            ui_elements = [UIElement.from_dict(e) for e in raw_elements]
            try:
                batch_limit = max(20, int(vlm_batch_max_elements))
                if len(ui_elements) <= batch_limit:
                    ui_elements = vlm_client.classify_elements_batch(
                        image_path=session_preprocessed,
                        elements=ui_elements,
                        max_retries=2,
                        timeout_seconds=ollama_timeout_seconds or 60.0,
                    )
                else:
                    merged: List[UIElement] = []
                    for start in range(0, len(ui_elements), batch_limit):
                        chunk = ui_elements[start:start + batch_limit]
                        chunk = vlm_client.classify_elements_batch(
                            image_path=session_preprocessed,
                            elements=chunk,
                            max_retries=2,
                            timeout_seconds=ollama_timeout_seconds or 60.0,
                        )
                        merged.extend(chunk)
                    ui_elements = merged
                payload["elements"] = [e.to_dict() for e in ui_elements]
            except Exception as exc:
                logging.warning("Batch VLM classification failed: %s", exc)

        with open(final_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    else:
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
    global current_session, processing_inflight
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
                processing_inflight[session_id] = processing_inflight.get(session_id, 0) + 1

            with session_lock:
                session = sessions_by_id.get(session_id)

            if not session:
                logging.warning("Dropping frame for unknown session_id=%s", session_id)
                continue

            _process_single_frame_item(session, session_id, frame_path)

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
        finally:
            with session_lock:
                if session_id in processing_inflight:
                    processing_inflight[session_id] = max(0, processing_inflight[session_id] - 1)
                    if processing_inflight[session_id] == 0:
                        del processing_inflight[session_id]


@app.get("/vision/diagnose")
def vision_diagnose():
    """
    Run pre-flight checks and report what is available:
    camera, VLM providers, installed packages.
    """
    results: Dict[str, Any] = {}

    # --- camera probe ---
    camera_ok = False
    try:
        import cv2 as _cv2
        backend = _cv2.CAP_DSHOW if os.name == "nt" else 0
        cap = _cv2.VideoCapture(0, backend)
        camera_ok = cap.isOpened()
        cap.release()
    except Exception as _exc:
        results["camera_error"] = str(_exc)
    results["camera_index_0_available"] = camera_ok

    # --- VLM provider availability ---
    providers: Dict[str, Any] = {}

    # ollama
    try:
        from urllib import request as _req
        r = _req.urlopen("http://127.0.0.1:11434/api/tags", timeout=3)
        import json as _json
        tags = _json.loads(r.read())
        providers["ollama"] = {
            "available": True,
            "models": [m["name"] for m in tags.get("models", [])],
        }
    except Exception as _exc:
        providers["ollama"] = {"available": False, "reason": str(_exc)}

    # torch / local
    try:
        import torch  # type: ignore
        providers["local"] = {"available": True, "cuda": torch.cuda.is_available()}
    except ImportError:
        providers["local"] = {"available": False, "reason": "torch not installed"}

    # anthropic
    try:
        import anthropic  # type: ignore  # noqa: F401
        providers["claude"] = {
            "available": True,
            "api_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        }
    except ImportError:
        providers["claude"] = {"available": False, "reason": "anthropic not installed"}

    # openai
    try:
        import openai  # type: ignore  # noqa: F401
        providers["gpt4v"] = {
            "available": True,
            "api_key_set": bool(os.getenv("OPENAI_API_KEY")),
        }
    except ImportError:
        providers["gpt4v"] = {"available": False, "reason": "openai not installed"}

    results["vlm_providers"] = providers

    # --- recommended start params ---
    recommended_provider = "no_vlm"
    if providers.get("ollama", {}).get("available"):
        ollama_models = providers["ollama"].get("models", [])
        recommended_provider = f"ollama  (models: {', '.join(ollama_models) or 'none pulled yet'})"
    elif providers.get("claude", {}).get("api_key_set"):
        recommended_provider = "claude"
    elif providers.get("gpt4v", {}).get("api_key_set"):
        recommended_provider = "gpt4v"
    elif providers.get("local", {}).get("available"):
        recommended_provider = "local"

    results["recommended_provider"] = recommended_provider
    results["recommended_start_params"] = (
        "POST /vision/start?camera_index=0&save_interval=1"
        "&provider=ollama&no_vlm=false"
        if providers.get("ollama", {}).get("available")
        else "POST /vision/start?camera_index=0&save_interval=1&no_vlm=true"
    )

    return results


@app.post("/vision/start")
def start_vision(
    camera_index: int = 1,
    save_interval: float = 1.0,
    provider: str = "ollama",
    local_model: str = "llava:7b",
    ollama_base_url: Optional[str] = None,
    ollama_timeout_seconds: float = 45.0,
    coarse_max_boxes: int = 180,
    refined_max_elements: int = 120,
    vlm_batch_max_elements: int = 90,
    no_vlm: bool = False,
):
    """Start continuous capture + processing session.

    Each processed frame is appended to a SessionAggregator.  When the
    session is stopped via ``/vision/stop`` a single ``session_summary.json``
    is written to the session root directory.
    """
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

    session = _new_session(prefix="session", aggregate=True)
    session.update(
        {
            "camera_index": camera_index,
            "save_interval": save_interval,
            "provider": provider,
            "local_model": local_model,
            "ollama_base_url": ollama_base_url,
            "ollama_timeout_seconds": ollama_timeout_seconds,
            "coarse_max_boxes": coarse_max_boxes,
            "refined_max_elements": refined_max_elements,
            "vlm_batch_max_elements": vlm_batch_max_elements,
            "no_vlm": no_vlm,
            "vlm_client": vlm_client,
        }
    )

    with session_lock:
        current_session = session
        capture_running = True
        sessions_by_id[session["id"]] = session

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
        "ollama_timeout_seconds": ollama_timeout_seconds,
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

    if wait_for_processing:
        deadline = time.time() + max(0.0, processing_timeout)
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

        # If background worker could not clear the queue within timeout,
        # process remaining frames synchronously so summary is complete.
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
                logging.exception("Synchronous drain processing failed: %s", exc)

    # Finalise SessionAggregator → writes session_summary.json
    session_summary_path: Optional[str] = None
    session_doc: Optional[Dict[str, Any]] = None
    agg = session.get("aggregator")
    if agg is not None and agg.is_active:
        try:
            session_doc = agg.finalize(save=True)
            session_summary_path = str(
                Path(session["root"]) / f"{agg.session_id}_summary.json"
            )
            logging.info(
                "Session summary saved: %s  screens=%d",
                session_summary_path, session_doc.get("screen_count", 0),
            )
        except Exception as _fin_exc:
            logging.warning("SessionAggregator.finalize failed: %s", _fin_exc)

    summary = {
        "status": "stopped",
        "session_id": session["id"],
        "session_root": session["root"],
        "session_summary_path": session_summary_path,
        "raw_frames": len(list(Path(session["raw_dir"]).glob("*.jpg"))),
        "preprocessed_frames": len(list(Path(session["preproc_dir"]).glob("*.jpg"))),
        "final_json": len(list(Path(session["final_dir"]).glob("*.json"))),
        # Full aggregated session document — one JSON with all screen data
        "session_data": session_doc,
    }

    with session_lock:
        current_session = None
        sessions_by_id.pop(session["id"], None)

    return summary


@app.post("/vision/capture")
def capture_once(
    camera_index: int = 1,
    provider: str = "ollama",
    local_model: str = "llava:7b",
    ollama_base_url: Optional[str] = None,
    ollama_timeout_seconds: float = 60.0,
    coarse_max_boxes: int = 180,
    refined_max_elements: int = 120,
    vlm_batch_max_elements: int = 90,
    no_vlm: bool = False,
):
    """Single-shot capture and pipeline execution. Returns final JSON.

    VLM classification uses a single batch call for all detected elements.
    """
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
            ollama_timeout_seconds=ollama_timeout_seconds,
            coarse_max_boxes=coarse_max_boxes,
            refined_max_elements=refined_max_elements,
            vlm_batch_max_elements=vlm_batch_max_elements,
        )
        return result
    except Exception as e:
        logging.exception("Single-shot pipeline failed")
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
        "camera_index": session.get("camera_index") if session else None,
        "provider": session.get("provider") if session else None,
        "no_vlm": session.get("no_vlm") if session else None,
    }
