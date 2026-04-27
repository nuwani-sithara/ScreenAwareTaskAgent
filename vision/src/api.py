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
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from src.capture.webcam_capture import start_webcam_stream
from src.preprocessing.preprocess import preprocess_all
from src.perception.grounding.bbox_element_enricher import enrich_frame
from src.perception.vlm import get_vlm_client, UIElement, get_ui_discovery_prompt
from src.session_aggregator import SessionAggregator

if TYPE_CHECKING:
    from src.vision.pipeline import VisionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
            dedup_frames=False,
        )
        agg.start(session_id=session_id)
        session["aggregator"] = agg
    return session


def _init_vlm_client(no_vlm: bool):
    if no_vlm:
        logger.info("VLM disabled via no_vlm flag")
        return None
    logger.info("Initializing Gemini VLM client")
    return get_vlm_client()


def _init_semantic_pipeline(no_vlm: bool) -> Optional["VisionPipeline"]:
    """Initialize the Gemini semantic pipeline when requested."""
    if no_vlm:
        return None
    from src.vision.pipeline import VisionPipeline

    logger.info("Initializing Gemini semantic pipeline")
    return VisionPipeline()


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


def _item_to_bbox_norm(item: Dict[str, Any]) -> Tuple[float, float, float, float]:
    bbox = item.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return tuple(float(v) for v in bbox)

    dxdy = item.get("dxdy")
    screen_bbox = item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0])
    if (
        isinstance(dxdy, (list, tuple))
        and len(dxdy) == 4
        and isinstance(screen_bbox, (list, tuple))
        and len(screen_bbox) == 4
    ):
        dx1, dy_top, dx2, dy_bottom = (float(v) for v in dxdy)
        sx1, sy1, sx2, sy2 = (float(v) for v in screen_bbox)
        sw = max(1e-9, sx2 - sx1)
        sh = max(1e-9, sy2 - sy1)
        return (
            max(0.0, min(1.0, sx1 + dx1 * sw)),
            max(0.0, min(1.0, sy1 + dy_top * sh)),
            max(0.0, min(1.0, sx1 + dx2 * sw)),
            max(0.0, min(1.0, sy2 - dy_bottom * sh)),
        )
    return (0.0, 0.0, 1.0, 1.0)


def _norm_bbox(
    bbox: Tuple[float, float, float, float],
) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = (float(v) for v in bbox)
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    return (
        max(0.0, min(1.0, x1)),
        max(0.0, min(1.0, y1)),
        max(0.0, min(1.0, x2)),
        max(0.0, min(1.0, y2)),
    )


def _bbox_area_px(
    bbox: Tuple[float, float, float, float],
    image_w: int,
    image_h: int,
) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, (x2 - x1) * image_w) * max(0.0, (y2 - y1) * image_h)


def _bbox_center_xy(
    bbox: Tuple[float, float, float, float],
    image_w: int,
    image_h: int,
) -> Tuple[int, int]:
    x1, y1, x2, y2 = bbox
    cx = int(round(((x1 + x2) * 0.5) * image_w))
    cy = int(round(((y1 + y2) * 0.5) * image_h))
    return max(0, min(image_w - 1, cx)), max(0, min(image_h - 1, cy))


def is_inside(
    inner_bbox: Tuple[float, float, float, float],
    outer_bbox: Tuple[float, float, float, float],
    min_ratio: float = 0.97,
) -> bool:
    return _bbox_contained_ratio_norm(inner_bbox, outer_bbox) >= min_ratio


def apply_nms(
    detections: List[Dict[str, Any]],
    iou_threshold: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Remove overlapping boxes by IoU, keeping highest confidence per region.
    """
    if not detections:
        return []
    ranked = sorted(
        detections,
        key=lambda d: float(d.get("confidence", 0.0)),
        reverse=True,
    )
    kept: List[Dict[str, Any]] = []
    for cand in ranked:
        cb = _item_to_bbox_norm(cand)
        suppress = False
        for ex in kept:
            eb = _item_to_bbox_norm(ex)
            if _bbox_iou_norm(cb, eb) > iou_threshold:
                suppress = True
                break
        if not suppress:
            kept.append(cand)
    return kept


def merge_nearby_elements(
    detections: List[Dict[str, Any]],
    image_w: int,
    image_h: int,
    distance_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Merge same-type detections when centers are very close and sizes are similar.
    """
    if not detections:
        return []
    used = [False] * len(detections)
    merged: List[Dict[str, Any]] = []

    if distance_threshold is None:
        # 2% of image diagonal (screen independent)
        distance_threshold = 0.02 * ((image_w ** 2 + image_h ** 2) ** 0.5)

    def _size_similar(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
        aw = max(1e-6, a[2] - a[0])
        ah = max(1e-6, a[3] - a[1])
        bw = max(1e-6, b[2] - b[0])
        bh = max(1e-6, b[3] - b[1])
        # Similar size within +/-25%
        rw = abs(aw - bw) / max(aw, bw)
        rh = abs(ah - bh) / max(ah, bh)
        return rw <= 0.25 and rh <= 0.25

    for i, base in enumerate(detections):
        if used[i]:
            continue
        used[i] = True
        bb = _item_to_bbox_norm(base)
        bcx, bcy = _bbox_center_xy(bb, image_w, image_h)
        btype = str(base.get("type", "unknown")).strip().lower()
        group = [base]

        for j in range(i + 1, len(detections)):
            if used[j]:
                continue
            cur = detections[j]
            ctype = str(cur.get("type", "unknown")).strip().lower()
            if ctype != btype:
                continue
            cb = _item_to_bbox_norm(cur)
            if not _size_similar(bb, cb):
                continue
            ccx, ccy = _bbox_center_xy(cb, image_w, image_h)
            dist = ((bcx - ccx) ** 2 + (bcy - ccy) ** 2) ** 0.5
            if dist <= distance_threshold:
                used[j] = True
                group.append(cur)

        if len(group) == 1:
            merged.append(base)
            continue

        boxes = [_item_to_bbox_norm(g) for g in group]
        x1 = min(b[0] for b in boxes)
        y1 = min(b[1] for b in boxes)
        x2 = max(b[2] for b in boxes)
        y2 = max(b[3] for b in boxes)
        best = max(group, key=lambda g: float(g.get("confidence", 0.0)))
        out = dict(best)
        out["bbox"] = [x1, y1, x2, y2]
        out["dxdy"] = [x1, y1, x2, max(0.0, min(1.0, 1.0 - y2))]
        cx, cy = _bbox_center_xy((x1, y1, x2, y2), image_w, image_h)
        out["dx"] = cx
        out["dy"] = cy
        out["confidence"] = max(float(g.get("confidence", 0.0)) for g in group)
        merged.append(out)

    return merged


def _remove_contained_elements_generic(
    detections: List[Dict[str, Any]],
    image_w: int,
    image_h: int,
) -> List[Dict[str, Any]]:
    """
    Generic hierarchy cleanup:
    if A is contained in B, keep the one with larger area AND higher confidence.
    """
    if not detections:
        return []
    container_types = {"card", "container", "form", "panel"}
    keep = [True] * len(detections)
    areas = [_bbox_area_px(_item_to_bbox_norm(d), image_w, image_h) for d in detections]
    confs = [float(d.get("confidence", 0.0)) for d in detections]

    for i in range(len(detections)):
        if not keep[i]:
            continue
        bi = _item_to_bbox_norm(detections[i])
        for j in range(i + 1, len(detections)):
            if not keep[j]:
                continue
            bj = _item_to_bbox_norm(detections[j])
            i_in_j = is_inside(bi, bj, min_ratio=0.97)
            j_in_i = is_inside(bj, bi, min_ratio=0.97)
            if not i_in_j and not j_in_i:
                continue

            if i_in_j:
                ti = str(detections[i].get("type", "unknown")).strip().lower()
                tj = str(detections[j].get("type", "unknown")).strip().lower()
                # Keep hierarchy under containers/forms/panels/cards.
                if tj in container_types:
                    continue
                # Type-aware removals for nested non-container controls.
                if ti == "text" and tj == "button":
                    keep[i] = False
                    continue
                if ti == "icon" and tj in {"button", "image"}:
                    keep[i] = False
                    continue
                # default: remove smaller/lower-confidence
                if areas[j] >= areas[i] and confs[j] >= confs[i]:
                    keep[i] = False
                else:
                    keep[j] = False
            elif j_in_i:
                ti = str(detections[i].get("type", "unknown")).strip().lower()
                tj = str(detections[j].get("type", "unknown")).strip().lower()
                if ti in container_types:
                    continue
                if tj == "text" and ti == "button":
                    keep[j] = False
                    continue
                if tj == "icon" and ti in {"button", "image"}:
                    keep[j] = False
                    continue
                if areas[i] >= areas[j] and confs[i] >= confs[j]:
                    keep[j] = False
                else:
                    keep[i] = False

    return [d for idx, d in enumerate(detections) if keep[idx]]


def _prune_icon_inside_image(
    detections: List[Dict[str, Any]],
    image_w: int,
    image_h: int,
) -> List[Dict[str, Any]]:
    if not detections:
        return []
    keep = [True] * len(detections)
    for i, a in enumerate(detections):
        if not keep[i]:
            continue
        ta = str(a.get("type", "unknown")).strip().lower()
        ba = _item_to_bbox_norm(a)
        area_a = _bbox_area_px(ba, image_w, image_h)
        for j, b in enumerate(detections):
            if i == j or not keep[j]:
                continue
            tb = str(b.get("type", "unknown")).strip().lower()
            bb = _item_to_bbox_norm(b)
            area_b = _bbox_area_px(bb, image_w, image_h)
            # icon inside image -> drop icon
            if ta == "icon" and tb == "image" and is_inside(ba, bb):
                keep[i] = False
                break
    return [d for idx, d in enumerate(detections) if keep[idx]]


def _filter_by_confidence(
    detections: List[Dict[str, Any]],
    threshold: float,
) -> List[Dict[str, Any]]:
    return [d for d in detections if float(d.get("confidence", 0.0)) >= threshold]


def _filter_by_min_area_ratio(
    detections: List[Dict[str, Any]],
    image_w: int,
    image_h: int,
    min_area_ratio: float = 0.001,
) -> List[Dict[str, Any]]:
    min_area = float(image_w * image_h) * float(min_area_ratio)
    out: List[Dict[str, Any]] = []
    for d in detections:
        b = _item_to_bbox_norm(d)
        area = _bbox_area_px(b, image_w, image_h)
        if area >= min_area:
            out.append(d)
    return out


def _merge_vlm_discovery_into_refined(
    refined_bboxes: List[Dict[str, Any]],
    vlm_elements: List[UIElement],
    image_w: int,
    image_h: int,
) -> List[Dict[str, Any]]:
    """
    Merge full-image VLM discovery with layout-based refined boxes.
    - If IoU with an existing box is high, enrich that box metadata.
    - Otherwise, append a new VLM-discovered box.
    """
    merged = list(refined_bboxes)
    by_idx_bbox = [_item_to_bbox_norm(item) for item in merged]

    for elem in vlm_elements:
        eb = _norm_bbox(elem.bbox)
        ex1, ey1, ex2, ey2 = eb
        if (ex2 - ex1) <= 1e-6 or (ey2 - ey1) <= 1e-6:
            continue

        best_iou = 0.0
        best_idx = -1
        for i, rb in enumerate(by_idx_bbox):
            iou = _bbox_iou_norm(eb, rb)
            if iou > best_iou:
                best_iou = iou
                best_idx = i

        if best_idx >= 0 and best_iou >= 0.62:
            target = merged[best_idx]
            target["type"] = str(elem.type or target.get("type", "unknown")).strip().lower() or target.get("type", "unknown")
            lbl = " ".join(str(elem.label or "").split()).strip()
            if lbl:
                target["label"] = lbl[:160]
            desc = str(elem.description or "").strip()
            if desc:
                target["description"] = desc
            st = str(elem.state or "").strip().lower()
            if st and st != "unknown":
                target["state"] = st
            target["confidence"] = max(float(target.get("confidence", 0.5)), float(elem.confidence or 0.5))
            target["source"] = "vlm_discovery"
            continue

        dx, dy = _bbox_center_xy(eb, image_w, image_h)
        merged.append(
            {
                "bbox": [float(v) for v in eb],
                "dxdy": [
                    float(ex1),
                    float(ey1),
                    float(ex2),
                    float(max(0.0, min(1.0, 1.0 - ey2))),
                ],
                "dx": dx,
                "dy": dy,
                "screen_bbox": [0.0, 0.0, 1.0, 1.0],
                "source": "vlm_discovery",
                "type": str(elem.type or "unknown").strip().lower() or "unknown",
                "label": " ".join(str(elem.label or "").split()).strip()[:160],
                "description": str(elem.description or "").strip(),
                "state": str(elem.state or "normal").strip().lower() or "normal",
                "confidence": max(0.0, min(1.0, float(elem.confidence or 0.5))),
            }
        )
        by_idx_bbox.append(eb)

    return merged


def _dedupe_and_rank_refined_bboxes(
    boxes: List[Dict[str, Any]],
    max_elements: int,
    image_w: Optional[int] = None,
    image_h: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if not boxes:
        return []

    source_weight = {
        "ui_detector": 1.00,
        "ocr_enriched": 0.98,
        "vlm_enriched": 0.99,
        "vlm_discovery": 1.02,
        "layout_form": 1.00,
        "layout_text": 0.95,
        "layout_adaptive": 0.85,
        "layout_edge": 0.75,
        "layout": 0.70,
    }

    def _score(item: Dict[str, Any]) -> float:
        bbox = _item_to_bbox_norm(item)
        x1, y1, x2, y2 = bbox
        area = max(1e-9, (x2 - x1) * (y2 - y1))
        conf = float(item.get("confidence", 0.5))
        sw = source_weight.get(str(item.get("source", "layout")), 0.65)
        edge_penalty = 0.0
        if area < 0.0012 and (y1 < 0.02 or y2 > 0.98):
            edge_penalty = 0.12
        return (0.65 * conf) + (0.35 * sw) - (0.05 * area) - edge_penalty

    ranked = sorted(boxes, key=_score, reverse=True)
    kept: List[Dict[str, Any]] = []

    container_types = {"card", "container", "form", "panel"}
    for candidate in ranked:
        cb = _item_to_bbox_norm(candidate)
        c_source = str(candidate.get("source", "layout"))
        c_type = str(candidate.get("type", "unknown")).strip().lower()
        if image_w and image_h:
            # Minimum size filter to drop tiny noisy fragments.
            if _bbox_area_px(cb, image_w, image_h) < 400.0:
                continue
        skip = False
        for existing in kept:
            eb = _item_to_bbox_norm(existing)
            e_type = str(existing.get("type", "unknown")).strip().lower()
            iou = _bbox_iou_norm(cb, eb)
            contained = _bbox_contained_ratio_norm(cb, eb)
            if iou >= 0.82:
                skip = True
                break
            # Do not collapse children of container-like layout elements.
            if contained >= 0.97 and c_source not in {"layout_text", "layout_form"} and e_type not in container_types:
                skip = True
                break
            # explicit nested cleanup
            if contained >= 0.97:
                if c_type == "text" and e_type == "button":
                    skip = True
                    break
                if c_type == "icon" and e_type in {"button", "image"}:
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
    for idx, item in enumerate(refined_bboxes):
        x1, y1, x2, y2 = _item_to_bbox_norm(item)
        src = str(item.get("source", "layout"))
        etype = str(item.get("type", "unknown"))
        conf = float(item.get("confidence", 0.0))
        color = (0, 255, 0)
        if src == "vlm_discovery":
            color = (255, 170, 0)
        elif src == "layout_text":
            color = (0, 200, 255)
        cv2.rectangle(
            vis,
            (int(x1 * w), int(y1 * h)),
            (int(x2 * w), int(y2 * h)),
            color,
            2,
        )
        text = f"{idx}:{etype} {conf:.2f}"
        tx = int(x1 * w)
        ty = max(10, int(y1 * h) - 4)
        cv2.putText(
            vis,
            text,
            (tx, ty),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            color,
            1,
            cv2.LINE_AA,
        )
    cv2.imwrite(out_path, vis)


def _functional_label(etype: str, dx: int, dy: int, elem_id: str) -> str:
    human = (etype or "element").replace("_", " ").strip()
    if human:
        if human == "input field":
            return "Input field"
        if human == "button":
            return "Button"
        if human == "link":
            return "Link"
        return human.capitalize()
    return "Element"


def _specific_description(etype: str, label: str, dx: int, dy: int) -> str:
    human = (etype or "element").replace("_", " ").strip()
    if label:
        return (
            f"{human.capitalize()} identified near ({dx},{dy}) with label '{label}', "
            "used in the current visible screen."
        )
    return (
        f"{human.capitalize()} identified near ({dx},{dy}) in the current visible screen."
    )


def _strip_internal_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the payload without internal-only fields."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    elements = out.get("elements", [])
    if isinstance(elements, list):
        cleaned_elements: List[Dict[str, Any]] = []
        for element in elements:
            if not isinstance(element, dict):
                cleaned_elements.append(element)
                continue
            cleaned = dict(element)
            cleaned.pop("bbox", None)
            cleaned_elements.append(cleaned)
        out["elements"] = cleaned_elements
    return out


def _finalize_elements_with_dxdy(
    payload: Dict[str, Any],
    image_width: int,
    image_height: int,
) -> Dict[str, Any]:
    elements = payload.get("elements", [])
    if not isinstance(elements, list):
        return payload

    screen_bbox = payload.get("screen_bbox")
    if isinstance(screen_bbox, (list, tuple)) and len(screen_bbox) == 4:
        try:
            sx1, sy1, sx2, sy2 = (float(v) for v in screen_bbox)
        except Exception:
            sx1, sy1, sx2, sy2 = 0.0, 0.0, float(image_width), float(image_height)
    else:
        sx1, sy1, sx2, sy2 = 0.0, 0.0, float(image_width), float(image_height)

    screen_size = payload.get("screen_size")
    if isinstance(screen_size, dict):
        try:
            screen_width = max(1, int(round(float(screen_size.get("width", sx2 - sx1)))))
            screen_height = max(1, int(round(float(screen_size.get("height", sy2 - sy1)))))
        except Exception:
            screen_width = max(1, int(round(sx2 - sx1)))
            screen_height = max(1, int(round(sy2 - sy1)))
    else:
        screen_width = max(1, int(round(sx2 - sx1)))
        screen_height = max(1, int(round(sy2 - sy1)))

    finalized: List[Dict[str, Any]] = []
    for elem in elements:
        if not isinstance(elem, dict):
            continue

        source = str(elem.get("source", "")).lower()
        etype = str(elem.get("type", "")).strip().lower()
        if not etype or etype == "unknown":
            if source == "layout_text":
                etype = "text"
            elif source == "layout_form":
                etype = "input_field"
            elif source == "layout_edge":
                etype = "image"
            else:
                etype = "text"
            elem["type"] = etype

        state = str(elem.get("state", "")).strip().lower()
        if not state or state == "unknown":
            state = "normal"

        label = " ".join(str(elem.get("label", "")).split()).strip()
        label = label[:160]

        desc = str(elem.get("description", "")).strip()
        if not desc or desc in {
            "No VLM available",
            "VLM classification failed",
            "Skipped VLM classification (provider budget)",
        }:
            desc = ""

        bbox = elem.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                x1 = float(bbox[0])
                y1 = float(bbox[1])
                x2 = float(bbox[2])
                y2 = float(bbox[3])
                cx = int(round(max(0.0, (x1 + x2) * 0.5)))
                cy = int(round(max(0.0, (y1 + y2) * 0.5)))
                elem["dx"] = max(0, min(screen_width, cx))
                elem["dy"] = max(0, min(screen_height, cy))
                elem["frame_bbox"] = [
                    max(0, min(image_width - 1, int(round(sx1 + x1)))),
                    max(0, min(image_height - 1, int(round(sy1 + y1)))),
                    max(0, min(image_width, int(round(sx1 + x2)))),
                    max(0, min(image_height, int(round(sy1 + y2)))),
                ]
                elem["frame_dx"] = max(0, min(image_width - 1, int(round(sx1 + cx))))
                elem["frame_dy"] = max(0, min(image_height - 1, int(round(sy1 + cy))))
            except Exception:
                pass
        try:
            dx = int(round(float(elem.get("dx", 0)))) if str(elem.get("dx", "")).strip() else 0
        except Exception:
            dx = 0
        try:
            dy = int(round(float(elem.get("dy", 0)))) if str(elem.get("dy", "")).strip() else 0
        except Exception:
            dy = 0
        dx = max(0, min(screen_width, dx))
        dy = max(0, min(screen_height, dy))

        frame_dx = elem.get("frame_dx")
        frame_dy = elem.get("frame_dy")
        if frame_dx is None:
            frame_dx = max(0, min(image_width - 1, int(round(sx1 + dx))))
        else:
            try:
                frame_dx = int(round(float(frame_dx)))
            except Exception:
                frame_dx = max(0, min(image_width - 1, int(round(sx1 + dx))))
        if frame_dy is None:
            frame_dy = max(0, min(image_height - 1, int(round(sy1 + dy))))
        else:
            try:
                frame_dy = int(round(float(frame_dy)))
            except Exception:
                frame_dy = max(0, min(image_height - 1, int(round(sy1 + dy))))

        # no coordinate-based label fallback

        confidence = elem.get("confidence", 0.5)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        final_source = str(elem.get("source", "")).strip() or "ui_detector"
        final_elem = {
            "id": str(elem.get("id", "elem_0")),
            "type": etype,
            "label": label,
            "description": desc if desc else _specific_description(etype, label, dx, dy),
            "state": state,
            "dx": dx,
            "dy": dy,
            "frame_dx": frame_dx,
            "frame_dy": frame_dy,
            "confidence": confidence,
            "source": final_source,
        }
        frame_bbox = elem.get("frame_bbox")
        if isinstance(frame_bbox, list) and len(frame_bbox) == 4:
            final_elem["frame_bbox"] = frame_bbox
        finalized.append(final_elem)
    payload["elements"] = finalized
    return payload


def _capture_single_frame(camera_index: int = 0):
    backend = cv2.CAP_DSHOW if os.name == "nt" else 0
    cap = cv2.VideoCapture(camera_index, backend)
    if not cap.isOpened():
        return None
    frame = None
    try:
        # Match the streaming path: try to negotiate a larger native frame size
        # instead of sticking to the camera default (often 640x480).
        try:
            cur_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            cur_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if max(cur_w, cur_h) <= 640:
                preferred = [(1920, 1080), (1280, 720), (1600, 1200), (1024, 768)]
                for pw, ph in preferred:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(pw))
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(ph))
                    rw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                    rh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                    if rw >= pw - 16 and rh >= ph - 16:
                        break
        except Exception:
            pass

        # Discard a few warm-up frames so the first read is not a black frame.
        for _ in range(8):
            ok, f = cap.read()
            if ok:
                frame = f
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if float(gray.mean()) > 8.0 and float(cv2.countNonZero(gray)) / float(gray.size) > 0.01:
                    break
            time.sleep(0.03)
    finally:
        cap.release()
    return frame


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _run_pipeline_for_frame(
    frame_path: str,
    session: Dict[str, Any],
    vlm_client=None,
    semantic_pipeline: Optional["VisionPipeline"] = None,
    coarse_max_boxes: int = 180,
    refined_max_elements: int = 120,
    vlm_batch_max_elements: int = 90,
) -> Dict[str, Any]:
    """
    Run the Gemini-only pipeline for one frame:
      preprocess → Gemini semantic analysis → save final JSON.

    The session still writes the expected artifact files, but it no longer
    invokes any non-Gemini detector or fallback vision backend.
    """
    frame_name = Path(frame_path).name
    frame_stem = Path(frame_path).stem
    logger.info(
        "Pipeline started frame=%s session_id=%s semantic=%s",
        frame_name,
        session["id"],
        semantic_pipeline is not None,
    )

    proc_root = os.path.join(session["proc_dir"], f"proc_{int(time.time())}_{uuid.uuid4().hex[:6]}")
    proc_raw = os.path.join(proc_root, "raw_frames")
    proc_pre = os.path.join(proc_root, "preprocessed_frames")
    os.makedirs(proc_raw, exist_ok=True)
    os.makedirs(proc_pre, exist_ok=True)

    isolated_raw = os.path.join(proc_raw, frame_name)
    shutil.copyfile(frame_path, isolated_raw)
    logger.debug("Copied raw frame to %s", isolated_raw)

    logger.info("Running preprocessing for %s", frame_name)
    preprocess_all(raw_dir=proc_raw, out_dir=proc_pre)
    preprocessed_image = os.path.join(proc_pre, frame_name)

    # Persist preprocessed image in session folder
    session_preprocessed = os.path.join(session["preproc_dir"], frame_name)
    shutil.copyfile(preprocessed_image, session_preprocessed)
    logger.debug("Persisted preprocessed frame to %s", session_preprocessed)

    image = cv2.imread(preprocessed_image)
    if image is None:
        raise RuntimeError(f"Failed to read preprocessed frame: {preprocessed_image}")

    # Gemini semantic path:
    # - semantic VLM returns dx/dy points (no bbox)
    # - validation/overlay are handled inside VisionPipeline
    # - keep existing output file pattern for session compatibility
    if semantic_pipeline is not None:
        logger.info("Using Gemini semantic pipeline for %s", frame_name)
        img_h, img_w = image.shape[:2]

        coarse_json_path = os.path.join(session["coarse_dir"], f"{frame_stem}.json")
        with open(coarse_json_path, "w", encoding="utf-8") as f:
            json.dump({"bboxes": []}, f, indent=2)
        logger.debug("Wrote semantic placeholder coarse JSON to %s", coarse_json_path)

        # Respect provider-advised backoff to avoid repeated quota hammering.
        next_allowed = float(session.get("semantic_next_allowed_at", 0.0) or 0.0)
        now_ts = time.time()
        if next_allowed > now_ts:
            logger.info("Gemini backoff active for %.1fs before processing %s", next_allowed - now_ts, frame_name)
            time.sleep(min(30.0, next_allowed - now_ts))

        logger.info("Calling semantic pipeline for %s", frame_name)
        semantic_result = semantic_pipeline.run(preprocessed_image)
        logger.debug("Semantic pipeline result keys: %s", sorted(semantic_result.keys()))
        payload = semantic_result.get("vision_output", {})
        payload = _finalize_elements_with_dxdy(payload, img_w, img_h)
        semantic_error = str(semantic_result.get("vlm_error_type", "")).strip().lower()
        retry_after = float(semantic_result.get("vlm_retry_after_seconds", 0.0) or 0.0)
        logger.info(
            "Semantic pipeline completed frame=%s elements=%d error_type=%s retry_after=%.1f",
            frame_name,
            payload.get("element_count", 0) if isinstance(payload, dict) else 0,
            semantic_error or "none",
            retry_after,
        )

        # Gemini-only retry path for quota/rate limiting.
        if semantic_error == "quota_exceeded" and retry_after > 0.0:
            wait_s = min(30.0, retry_after + 0.5)
            session["semantic_next_allowed_at"] = time.time() + wait_s
            logger.warning("Gemini quota/rate limit. Retrying this frame in %.1fs", wait_s)
            time.sleep(wait_s)
            semantic_result = semantic_pipeline.run(preprocessed_image)
            payload = semantic_result.get("vision_output", {})
            payload = _finalize_elements_with_dxdy(payload, img_w, img_h)
            semantic_error = str(semantic_result.get("vlm_error_type", "")).strip().lower()
            retry_after = float(semantic_result.get("vlm_retry_after_seconds", 0.0) or 0.0)
        if semantic_error == "quota_exceeded" and retry_after > 0.0:
            session["semantic_next_allowed_at"] = time.time() + min(30.0, retry_after + 0.5)

        semantic_has_elements = bool(isinstance(payload, dict) and int(payload.get("element_count", 0) or 0) > 0)

        final_json_path = os.path.join(session["final_dir"], f"{frame_stem}.json")
        refined_json_path = os.path.join(session["refined_dir"], f"{frame_stem}.json")
        coarse_json_path = os.path.join(session["coarse_dir"], f"{frame_stem}.json")

        if semantic_has_elements:
            logger.debug("Gemini returned elements; writing semantic session artifacts")
        else:
            logger.warning("Gemini semantic pipeline returned zero elements; keeping empty Gemini output")

        with open(coarse_json_path, "w", encoding="utf-8") as f:
            json.dump({"bboxes": []}, f, indent=2)
        with open(refined_json_path, "w", encoding="utf-8") as f:
            json.dump({"bboxes": []}, f, indent=2)

        debug_image_path = os.path.join(session["refined_debug_dir"], frame_name)
        generated_debug = semantic_result.get("debug_image")
        if isinstance(generated_debug, str) and generated_debug and os.path.exists(generated_debug):
            try:
                shutil.copyfile(generated_debug, debug_image_path)
                logger.debug("Copied semantic debug image to %s", debug_image_path)
            except Exception as exc:
                logger.warning("Failed to copy semantic debug image: %s", exc)

        final_payload = _strip_internal_fields(payload)
        with open(final_json_path, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, indent=2)

        payload = _finalize_elements_with_dxdy(payload, image.shape[1], image.shape[0])
        final_payload = _strip_internal_fields(payload)
        with open(final_json_path, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, indent=2)

        return {
            "status": "completed",
            "session_id": session["id"],
            "source_frame": frame_path,
            "processed_at": time.time(),
            "final_json_path": final_json_path,
            "vision_data": final_payload,
        }

    final_json_path = os.path.join(session["final_dir"], f"{frame_stem}.json")
    empty_payload = {
        "image": preprocessed_image,
        "image_size": {"width": image.shape[1], "height": image.shape[0]},
        "coordinate_system": "pixel",
        "element_count": 0,
        "elements": [],
    }
    with open(final_json_path, "w", encoding="utf-8") as f:
        json.dump(empty_payload, f, indent=2)
    return {
        "status": "completed",
        "session_id": session["id"],
        "source_frame": frame_path,
        "processed_at": time.time(),
        "final_json_path": final_json_path,
        "vision_data": empty_payload,
    }


def webcam_capture_loop(camera_index: int, save_dir: str, save_interval: float = 1.0, cam_width: int | None = None, cam_height: int | None = None):
    """Capture loop with basic change detection. Enqueues frame paths for processing."""
    global capture_running, latest_frame, latest_result

    logger.info(
        "Webcam capture loop started camera_index=%s save_dir=%s interval=%.2f",
        camera_index,
        save_dir,
        save_interval,
    )
    os.makedirs(save_dir, exist_ok=True)

    last_saved = 0.0
    last_saved_small = None

    try:
        stream = start_webcam_stream(camera_index, width=cam_width, height=cam_height)
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
        logger.exception("Webcam error: %s", e)

    logger.info("Webcam capture loop stopped")


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

        except Exception as e:
            logger.exception("Per-frame pipeline failed")
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
    camera, Gemini VLM, installed packages.
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

    # --- Gemini availability ---
    providers: Dict[str, Any] = {}
    try:
        import google.generativeai  # type: ignore  # noqa: F401
        providers["gemini"] = {
            "available": True,
            "api_key_set": bool(os.getenv("GEMINI_API_KEY")),
            "mode": "semantic_dxdy_pipeline",
        }
    except ImportError:
        providers["gemini"] = {"available": False, "reason": "google-generativeai not installed"}

    results["vlm_providers"] = providers

    # --- recommended start params ---
    recommended_provider = "no_vlm"
    if providers.get("gemini", {}).get("api_key_set"):
        recommended_provider = "gemini"

    results["recommended_provider"] = recommended_provider
    if providers.get("gemini", {}).get("api_key_set"):
        results["recommended_start_params"] = (
            "POST /vision/start?camera_index=0&save_interval=1"
            "&no_vlm=false"
        )
    else:
        results["recommended_start_params"] = (
            "POST /vision/start?camera_index=0&save_interval=1&no_vlm=true"
        )

    return results


@app.post("/vision/start")
def start_vision(
    camera_index: int = 0,
    save_interval: float = 1.0,
    camera_width: int | None = None,
    camera_height: int | None = None,
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
    logger.info(
        "Received /vision/start camera_index=%s save_interval=%.2f no_vlm=%s",
        camera_index,
        save_interval,
        no_vlm,
    )

    with session_lock:
        if capture_running and current_session:
            logger.info("Vision session already running session_id=%s", current_session.get("id"))
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
            "camera_index": camera_index,
            "camera_width": camera_width,
            "camera_height": camera_height,
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
    logger.info("Vision session started session_id=%s root=%s", session["id"], session["root"])

    capture_thread = threading.Thread(
        target=webcam_capture_loop,
        args=(camera_index, session["raw_dir"], save_interval, camera_width, camera_height),
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
                logger.exception("Synchronous drain processing failed: %s", exc)

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
        # Full aggregated session document — one JSON with all screen data
        "session_data": session_doc,
    }

    with session_lock:
        current_session = None
        sessions_by_id.pop(session["id"], None)

    logger.info("Vision session stopped session_id=%s", session["id"])

    return summary


@app.post("/vision/capture")
def capture_once(
    camera_index: int = 0,
    coarse_max_boxes: int = 180,
    refined_max_elements: int = 120,
    vlm_batch_max_elements: int = 90,
    no_vlm: bool = False,
    use_current_session: bool = True,
):
    """Single-shot capture and pipeline execution. Returns final JSON.

    VLM classification uses a single batch call for all detected elements.
    """
    # Fast path: while streaming is active, grab the latest stream frame and
    # process it synchronously in the same session without stopping streaming.
    if use_current_session:
        with session_lock:
            active_session = current_session if capture_running and current_session else None
            frame_snapshot = latest_frame.copy() if active_session is not None and latest_frame is not None else None
        if active_session is not None:
            if frame_snapshot is None:
                return {
                    "status": "error",
                    "detail": "Streaming is active but no frame is available yet. Try again shortly.",
                    "session_id": active_session.get("id"),
                }
            frame_name = f"instant_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
            frame_path = os.path.join(active_session["raw_dir"], frame_name)
            cv2.imwrite(frame_path, frame_snapshot)
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

    frame = _capture_single_frame(camera_index=camera_index)
    if frame is None:
        return {"status": "error", "detail": f"Failed to capture frame from camera {camera_index}"}

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
        "camera_index": session.get("camera_index") if session else None,
        "no_vlm": session.get("no_vlm") if session else None,
        "vlm": "gemini" if session and session.get("vlm_client") is not None else "disabled",
    }

