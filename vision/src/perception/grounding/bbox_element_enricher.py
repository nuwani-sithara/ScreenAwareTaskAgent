"""
Enrich refined bounding boxes with semantic element metadata using a local VLM.

Input:
- data/preprocessed_frames/*.jpg
- data/refined_bboxes/*.json

Output:
- data/final_elements/*.json
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# OCR import (graceful degradation when Tesseract/Paddle not installed)
# ---------------------------------------------------------------------------
try:
    _src_dir = str(Path(__file__).resolve().parents[2])
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)
    from ocr import extract_text_from_region as _ocr_extract
    _OCR_AVAILABLE = True
except Exception:
    _OCR_AVAILABLE = False
    def _ocr_extract(image, bbox, w=None, h=None):  # type: ignore
        return ""

# ---------------------------------------------------------------------------
# Per-call frame-hash cache: skip re-enriching identical frames
# ---------------------------------------------------------------------------
_frame_hash_cache: Dict[str, List[Dict[str, Any]]] = {}


def _compute_frame_hash(image_path: str) -> str:
    """Return a SHA-256 hex digest of the raw image file bytes."""
    h = hashlib.sha256()
    with open(image_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Per-session crop-level VLM cache: crop_hash -> meta dict
# Prevents duplicate VLM calls for visually identical element crops.
_crop_vlm_cache: Dict[str, Dict[str, Any]] = {}


def _to_pixel_bbox(
    bbox_norm: Tuple[float, float, float, float], width: int, height: int
) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox_norm
    x1 = max(0, min(width - 1, int(x1 * width)))
    y1 = max(0, min(height - 1, int(y1 * height)))
    x2 = max(1, min(width, int(x2 * width)))
    y2 = max(1, min(height, int(y2 * height)))
    if x2 <= x1:
        x2 = min(width, x1 + 1)
    if y2 <= y1:
        y2 = min(height, y1 + 1)
    return x1, y1, x2, y2


def _safe_str(v: Any) -> str:
    return "" if v is None else str(v)


def _dxdy_to_bbox(
    dxdy: Tuple[float, float, float, float],
    screen_bbox: Tuple[float, float, float, float],
) -> Tuple[float, float, float, float]:
    dx1, dy_top, dx2, dy_bottom = dxdy
    sx1, sy1, sx2, sy2 = screen_bbox
    sw = max(1e-9, sx2 - sx1)
    sh = max(1e-9, sy2 - sy1)
    x1 = sx1 + dx1 * sw
    y1 = sy1 + dy_top * sh
    x2 = sx1 + dx2 * sw
    y2 = sy2 - dy_bottom * sh
    return (
        max(0.0, min(1.0, x1)),
        max(0.0, min(1.0, y1)),
        max(0.0, min(1.0, x2)),
        max(0.0, min(1.0, y2)),
    )


def _item_to_bbox(item: Dict[str, Any]) -> Tuple[float, float, float, float]:
    bbox = item.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return tuple(float(v) for v in bbox)

    dxdy = item.get("dxdy")
    screen_bbox = item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0])
    if isinstance(dxdy, (list, tuple)) and len(dxdy) == 4:
        return _dxdy_to_bbox(
            tuple(float(v) for v in dxdy),
            tuple(float(v) for v in screen_bbox),
        )
    return (0.0, 0.0, 1.0, 1.0)


def _bbox_to_dxdy_pixels(
    bbox: Tuple[float, float, float, float],
    screen_bbox: Tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> Tuple[int, int]:
    """DEPRECATED: top-left offset from screen edge.  Use _bbox_center_pixels."""
    x1, y1, _, _ = bbox
    sx1, sy1, _, _ = screen_bbox
    screen_x1 = sx1 * image_width
    screen_y1 = sy1 * image_height
    elem_x1 = x1 * image_width
    elem_y1 = y1 * image_height
    dx = int(round(max(0.0, elem_x1 - screen_x1)))
    dy = int(round(max(0.0, elem_y1 - screen_y1)))
    return dx, dy


def _bbox_center_pixels(
    bbox: Tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> Tuple[int, int]:
    """
    Return the CENTER of the bounding box as full-image pixel coordinates.
    These are the accurate click coordinates (dx, dy) that the agent needs.

    dx = center-x relative to full original screen image
    dy = center-y relative to full original screen image
    """
    x1, y1, x2, y2 = bbox
    cx = int(round((x1 + x2) / 2.0 * image_width))
    cy = int(round((y1 + y2) / 2.0 * image_height))
    return cx, cy


def _expand_bbox_norm(
    bbox_norm: Tuple[float, float, float, float],
    pad_ratio: float = 0.08,
) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox_norm
    bw = max(1e-6, x2 - x1)
    bh = max(1e-6, y2 - y1)
    padx = bw * pad_ratio
    pady = bh * pad_ratio
    return (
        max(0.0, x1 - padx),
        max(0.0, y1 - pady),
        min(1.0, x2 + padx),
        min(1.0, y2 + pady),
    )


def _prepare_crop_for_vlm(crop: np.ndarray, min_side: int = 224) -> np.ndarray:
    if crop.size == 0:
        return crop
    h, w = crop.shape[:2]
    if min(h, w) >= min_side:
        return crop
    scale = float(min_side) / float(max(1, min(h, w)))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def _heuristic_meta(crop: np.ndarray, source: str = "") -> Dict[str, Any]:
    if crop.size == 0:
        return {
            "type": "unknown",
            "label": "",
            "description": "Empty crop",
            "state": "unknown",
            "confidence": 0.1,
        }

    h, w = crop.shape[:2]
    area = h * w
    ar = w / max(1.0, h)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.sum(edges > 0)) / float(max(1, area))
    text_mask = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        17,
        3,
    )
    text_density = float(np.sum(text_mask > 0)) / float(max(1, area))

    # ------------------------------------------------------------------
    # Generalised multi-class heuristic (not form-only)
    # ------------------------------------------------------------------
    # Determine element type from visual cues; supports browser, IDE,
    # dashboard, terminal and arbitrary screen content.
    if text_density > 0.35 and area < 8000:
        element_type = "icon"
    elif source == "layout_text" or (text_density > 0.18 and edge_density < 0.18):
        element_type = "text"
    elif ar >= 5.0 and h <= 60:
        # Very wide, short strip → likely a navbar or toolbar
        element_type = "navbar"
    elif ar >= 2.5 and h <= 80:
        # Wide, short → input field or button depending on edge activity
        element_type = "input_field" if edge_density < 0.14 else "button"
    elif 1.5 <= ar < 2.5 and h <= 80 and edge_density >= 0.08:
        element_type = "button"
    elif ar < 1.2 and h <= 28 and w <= 28:
        element_type = "checkbox"
    elif source == "layout_edge" and area > 80000 and edge_density < 0.10:
        element_type = "image"
    elif source == "layout_edge" and area > 200000:
        # Large bordered region → card or modal
        element_type = "card"
    elif text_density > 0.10 and ar >= 1.3:
        element_type = "text"
    else:
        element_type = "unknown"

    return {
        "type": element_type,
        "label": "",
        "description": "Heuristic pre-classification",
        "state": "normal" if element_type != "unknown" else "unknown",
        "confidence": 0.35 if element_type != "unknown" else 0.15,
    }


def _classify_crop_with_vlm(
    vlm_client,
    crop_path: str,
    type_hint: str = "unknown",
    ocr_label: str = "",
) -> Dict[str, Any]:
    """
    Ask VLM to classify one cropped UI region and generate a rich description.
    Returns fallback values on parse/model failure.
    """
    ocr_hint = f'OCR text already extracted from this region: "{ocr_label}".  ' if ocr_label else ""
    prompt = (
        "You are classifying a single cropped UI element from a screenshot of any application "
        "(browser, IDE, dashboard, terminal, etc.).\n"
        "Return ONLY valid JSON in this exact schema:\n"
        '{"elements":[{"id":"elem_0",'
        '"type":"button|input_field|dropdown|checkbox|icon|image|card|text|navbar|sidebar|modal|table|unknown",'
        '"label":"<exact visible text or short functional name>",'
        '"description":"<one sentence: mention visible text, color if notable, screen location, likely function>",'
        '"state":"normal|active|disabled|focused|selected|unknown",'
        '"bbox":[0,0,1,1],"confidence":0.0}]}\n'
        f"Detector hint: likely {type_hint}.  {ocr_hint}\n"
        "Rules:\n"
        "1. label must be the exact visible text if present; otherwise a concise functional name.\n"
        "2. description must mention: (a) visible text, (b) color if distinctive, "
        "(c) position on screen (top/bottom/left/right/center), (d) likely function.\n"
        "3. Never output generic descriptions like 'Detected button at (x,y)'.\n"
        "4. Return exactly one element object."
    )
    result = vlm_client.analyze_ui(crop_path, prompt=prompt)
    if not result.parse_successful or not result.elements:
        # Fallback parse: accept partial JSON without strict bbox fields.
        raw = getattr(result, "raw_response", None)
        if raw:
            try:
                text = re.sub(r"```json\s*", "", raw)
                text = re.sub(r"```", "", text)
                match = re.search(r"\{.*\}", text, re.DOTALL)
                parsed = json.loads(match.group(0) if match else text)
                if isinstance(parsed, dict) and "elements" in parsed and isinstance(parsed["elements"], list) and parsed["elements"]:
                    parsed = parsed["elements"][0]
                if isinstance(parsed, dict):
                    ptype = _safe_str(parsed.get("type", "unknown")) or "unknown"
                    plabel = _safe_str(parsed.get("label", ""))
                    pdesc = _safe_str(parsed.get("description", ""))
                    pstate = _safe_str(parsed.get("state", "unknown")) or "unknown"
                    pconf = parsed.get("confidence", 0.35)
                    try:
                        pconf = float(pconf)
                    except Exception:
                        pconf = 0.35
                    pconf = max(0.0, min(1.0, pconf))
                    return {
                        "type": ptype,
                        "label": plabel,
                        "description": pdesc,
                        "state": pstate,
                        "confidence": pconf,
                    }
            except Exception:
                pass
        return {
            "type": "unknown",
            "label": "",
            "description": "VLM classification failed",
            "state": "unknown",
            "confidence": 0.1,
        }

    elem = result.elements[0]
    return {
        "type": _safe_str(elem.type) or "unknown",
        "label": _safe_str(elem.label),
        "description": _safe_str(elem.description),
        "state": _safe_str(elem.state) or "unknown",
        "confidence": float(elem.confidence),
    }


def enrich_frame(
    image_path: Path,
    refined_bbox_path: Path,
    out_path: Path,
    vlm_client=None,
    ollama_call_budget: Optional[int] = None,
    ollama_timeout_seconds: Optional[float] = None,
) -> None:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Failed to read image: {image_path}")
    h, w = image.shape[:2]

    # ------------------------------------------------------------------
    # Frame-hash deduplication: skip enrichment when frame is unchanged
    # ------------------------------------------------------------------
    frame_hash = _compute_frame_hash(str(image_path))
    global _frame_hash_cache
    if frame_hash in _frame_hash_cache:
        cached_elements = _frame_hash_cache[frame_hash]
        payload = {
            "image": str(image_path),
            "image_size": {"width": w, "height": h},
            "element_count": len(cached_elements),
            "elements": cached_elements,
            "from_cache": True,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return

    with open(refined_bbox_path, "r", encoding="utf-8") as f:
        refined = json.load(f)
    boxes = refined.get("bboxes", [])

    # Ollama can be too slow when called once per box on dense UIs.
    # Use configurable budget/timeout so final JSON is still emitted.
    is_ollama_client = (
        vlm_client is not None and vlm_client.__class__.__name__ == "OllamaVLMClient"
    )
    original_timeout = None
    if is_ollama_client and hasattr(vlm_client, "timeout_seconds"):
        try:
            original_timeout = float(vlm_client.timeout_seconds)
            if ollama_timeout_seconds is not None:
                vlm_client.timeout_seconds = max(1.0, float(ollama_timeout_seconds))
        except Exception:
            original_timeout = None
    if is_ollama_client:
        if ollama_call_budget is None:
            max_vlm_calls = len(boxes)
        else:
            max_vlm_calls = max(0, int(ollama_call_budget))
    else:
        max_vlm_calls = len(boxes)
    vlm_calls_used = 0

    elements: List[Dict[str, Any]] = []
    try:
        for idx, item in enumerate(boxes):
            bbox = _item_to_bbox(item)
            screen_bbox = tuple(item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0]))
            expanded_bbox = _expand_bbox_norm(bbox, pad_ratio=0.10)
            x1, y1, x2, y2 = _to_pixel_bbox(expanded_bbox, w, h)
            crop = image[y1:y2, x1:x2]
            crop = _prepare_crop_for_vlm(crop, min_side=224)
            heuristic = _heuristic_meta(crop, source=_safe_str(item.get("source", "")))

            # ----------------------------------------------------------
            # Accurate click coordinates: CENTER of bbox in full image
            # ----------------------------------------------------------
            cx, cy = _bbox_center_pixels(bbox, w, h)

            # ----------------------------------------------------------
            # OCR: extract real visible text for the label
            # ----------------------------------------------------------
            ocr_label = ""
            if _OCR_AVAILABLE:
                try:
                    ocr_label = _ocr_extract(image, bbox, w, h)
                except Exception:
                    ocr_label = ""

            meta = {
                "type": heuristic["type"],
                "label": ocr_label or heuristic["label"],
                "description": "No VLM available",
                "state": heuristic["state"],
                "confidence": max(float(item.get("confidence", 0.5)), float(heuristic["confidence"])),
            }

            should_call_vlm = (
                vlm_client is not None and crop.size > 0 and vlm_calls_used < max_vlm_calls
            )
            if should_call_vlm:
                # Crop-level VLM cache: avoid re-classifying identical element crops
                crop_hash = hashlib.sha256(crop.tobytes()).hexdigest()[:32]
                if crop_hash in _crop_vlm_cache:
                    meta = dict(_crop_vlm_cache[crop_hash])
                    # Prefer fresher OCR text over cached label when available
                    if ocr_label and not meta.get("label"):
                        meta["label"] = ocr_label
                else:
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        crop_path = tmp.name
                    try:
                        cv2.imwrite(crop_path, crop)
                        meta = _classify_crop_with_vlm(
                            vlm_client,
                            crop_path,
                            type_hint=heuristic["type"],
                            ocr_label=ocr_label,
                        )
                        # Prefer OCR text when VLM returned an empty or generic label
                        if ocr_label and not meta.get("label"):
                            meta["label"] = ocr_label
                        _crop_vlm_cache[crop_hash] = dict(meta)
                    except Exception:
                        meta = {
                            "type": heuristic["type"],
                            "label": ocr_label or heuristic["label"],
                            "description": "VLM classification failed",
                            "state": heuristic["state"],
                            "confidence": max(0.1, float(heuristic["confidence"])),
                        }
                    finally:
                        if os.path.exists(crop_path):
                            os.remove(crop_path)
                    vlm_calls_used += 1
            elif is_ollama_client:
                meta["description"] = "Skipped VLM classification (Ollama call budget)"

            elements.append(
                {
                    "id": f"elem_{idx}",
                    "type": meta["type"],
                    "label": meta["label"],
                    "description": meta["description"],
                    "state": meta["state"],
                    "dx": cx,
                    "dy": cy,
                    "dxdy": item.get("dxdy", []),
                    "screen_bbox": item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0]),
                    "confidence": meta["confidence"],
                    "source": "ui_detector",
                }
            )
    finally:
        if original_timeout is not None and hasattr(vlm_client, "timeout_seconds"):
            try:
                vlm_client.timeout_seconds = original_timeout
            except Exception:
                pass

    # Cache enriched result for this frame
    _frame_hash_cache[frame_hash] = elements

    payload = {
        "image": str(image_path),
        "image_size": {"width": w, "height": h},
        "element_count": len(elements),
        "elements": elements,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Enrich refined bbox JSON with element metadata.")
    parser.add_argument("--image-dir", default="data/preprocessed_frames")
    parser.add_argument("--refined-dir", default="data/refined_bboxes")
    parser.add_argument("--out-dir", default="data/final_elements")
    parser.add_argument("--provider", default="local", choices=["local", "claude", "gpt4v", "ollama"])
    parser.add_argument("--local-model", default="llava-hf/llava-1.5-7b-hf")
    parser.add_argument("--ollama-model", default="llava:7b")
    parser.add_argument(
        "--ollama-call-budget",
        type=int,
        default=None,
        help="Max element crops to send to Ollama per frame (default: all).",
    )
    parser.add_argument(
        "--ollama-timeout-seconds",
        type=float,
        default=None,
        help="Optional temporary Ollama timeout while enriching one frame.",
    )
    parser.add_argument("--no-vlm", action="store_true", help="Skip VLM classification and output unknown types.")
    args = parser.parse_args()

    # Late import so script can still run with --no-vlm in limited envs.
    vlm_client = None
    if not args.no_vlm:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from perception.vlm import get_vlm_client

        if args.provider == "local":
            kwargs = {"model_name": args.local_model}
        elif args.provider == "ollama":
            kwargs = {"model_name": args.ollama_model}
        else:
            kwargs = {}
        vlm_client = get_vlm_client(args.provider, **kwargs)

    image_dir = Path(args.image_dir)
    refined_dir = Path(args.refined_dir)
    out_dir = Path(args.out_dir)

    files = sorted(refined_dir.glob("*.json"))
    if not files:
        print(f"No refined bbox files found in {refined_dir}")
        return

    for f in files:
        image_path = image_dir / f"{f.stem}.jpg"
        if not image_path.exists():
            print(f"Skipping {f.name}: missing image {image_path.name}")
            continue

        out_path = out_dir / f"{f.stem}.json"
        enrich_frame(
            image_path,
            f,
            out_path,
            vlm_client=vlm_client,
            ollama_call_budget=args.ollama_call_budget,
            ollama_timeout_seconds=args.ollama_timeout_seconds,
        )
        print(f"[BBoxEnricher] Wrote {out_path.name}")


if __name__ == "__main__":
    main()
