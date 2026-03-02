"""
Enrich refined bounding boxes with semantic element metadata using a local VLM.

Input:
- data/preprocessed_frames/*.jpg
- data/refined_bboxes/*.json

Output:
- data/final_elements/*.json
"""

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import cv2
import numpy as np
from src.vision.ocr import extract_text_from_region
from src.vision.semantic_vlm import describe_ui_element


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


def _bbox_center_pixels(
    bbox: Tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> Tuple[int, int]:
    x1, y1, x2, y2 = bbox
    cx = int(round(((x1 + x2) * 0.5) * image_width))
    cy = int(round(((y1 + y2) * 0.5) * image_height))
    dx = max(0, min(image_width - 1, cx))
    dy = max(0, min(image_height - 1, cy))
    return dx, dy


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

    if source == "layout_text":
        element_type = "text"
    elif source == "layout_form":
        element_type = "input_field" if ar >= 2.0 else "button"
    elif ar >= 2.2 and h <= 120:
        element_type = "input_field" if edge_density < 0.14 else "button"
    elif 1.5 <= ar < 2.2 and h <= 90 and edge_density >= 0.08:
        element_type = "button"
    elif text_density > 0.20 and edge_density < 0.22:
        element_type = "text"
    elif source == "layout_edge" and area > 120000 and edge_density < 0.10:
        element_type = "image"
    else:
        element_type = "unknown"

    return {
        "type": element_type,
        "label": "",
        "description": "Heuristic classification",
        "state": "normal" if element_type != "unknown" else "unknown",
        "confidence": 0.35 if element_type != "unknown" else 0.15,
    }


def _classify_crop_with_vlm(
    vlm_client,
    crop_path: str,
    type_hint: str = "unknown",
) -> Dict[str, Any]:
    """
    Ask VLM to classify one cropped UI region.
    Returns fallback values on parse/model failure.
    """
    prompt = (
        "You are classifying a single cropped UI element from a screenshot.\n"
        "Return ONLY valid JSON in this exact schema:\n"
        "{\"elements\":[{\"id\":\"elem_0\",\"type\":\"button|input_field|text|label|icon|dropdown|checkbox|radio|menu|tab|modal|dialog|link|card|list_item|image|unknown\",\"label\":\"...\",\"description\":\"...\",\"state\":\"normal|active|disabled|focused|selected|unknown\",\"bbox\":[0,0,1,1],\"confidence\":0.0}]}\n"
        f"Hint from detector: likely {type_hint}.\n"
        "Rules: return exactly one element, prioritize visible text as label, and choose input_field/button/text when applicable."
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
            expanded_bbox = _expand_bbox_norm(bbox, pad_ratio=0.10)
            x1, y1, x2, y2 = _to_pixel_bbox(expanded_bbox, w, h)
            crop = image[y1:y2, x1:x2]
            crop = _prepare_crop_for_vlm(crop, min_side=224)
            heuristic = _heuristic_meta(crop, source=_safe_str(item.get("source", "")))
            dx, dy = _bbox_center_pixels(bbox, w, h)
            ocr_text = extract_text_from_region(image, bbox)
            detected_type = _safe_str(item.get("type", "")).strip().lower()
            seed_label = " ".join(_safe_str(item.get("label", "")).split()).strip()
            seed_description = _safe_str(item.get("description", "")).strip()
            seed_state = _safe_str(item.get("state", "")).strip().lower() or "normal"

            meta = {
                "type": detected_type if detected_type else heuristic["type"],
                "label": seed_label if seed_label else (ocr_text if ocr_text else heuristic["label"]),
                "description": seed_description,
                "state": seed_state if seed_state != "unknown" else heuristic["state"],
                "confidence": max(float(item.get("confidence", 0.5)), float(heuristic["confidence"])),
            }

            should_call_vlm = (
                vlm_client is not None and crop.size > 0 and vlm_calls_used < max_vlm_calls
            )
            if should_call_vlm:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    crop_path = tmp.name
                try:
                    cv2.imwrite(crop_path, crop)
                    meta = _classify_crop_with_vlm(
                        vlm_client,
                        crop_path,
                        type_hint=meta["type"],
                    )
                except Exception:
                    meta = {
                        "type": heuristic["type"],
                        "label": heuristic["label"],
                        "description": "VLM classification failed",
                        "state": heuristic["state"],
                        "confidence": max(0.1, float(heuristic["confidence"])),
                    }
                finally:
                    if os.path.exists(crop_path):
                        os.remove(crop_path)
                vlm_calls_used += 1
            elif is_ollama_client:
                meta["description"] = ""

            if not _safe_str(meta.get("label")).strip() and ocr_text:
                meta["label"] = ocr_text
            if not _safe_str(meta.get("description")).strip():
                meta["description"] = describe_ui_element(
                    vlm_client=None,
                    crop=crop,
                    label=_safe_str(meta.get("label")),
                    type_hint=_safe_str(meta.get("type", heuristic["type"])),
                )

            elements.append(
                {
                    "id": f"elem_{idx}",
                    "type": meta["type"],
                    "label": meta["label"],
                    "description": meta["description"],
                    "state": meta["state"],
                    "dx": int(item.get("dx", dx)),
                    "dy": int(item.get("dy", dy)),
                    "dxdy": item.get("dxdy", []),
                    "screen_bbox": item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0]),
                    "ocr_text": ocr_text,
                    "confidence": meta["confidence"],
                    "source": (
                        item.get("source", "ui_detector")
                        if str(item.get("source", "")).strip() == "vlm_discovery"
                        else ("ocr_enriched" if ocr_text else item.get("source", "ui_detector"))
                    ),
                }
            )
    finally:
        if original_timeout is not None and hasattr(vlm_client, "timeout_seconds"):
            try:
                vlm_client.timeout_seconds = original_timeout
            except Exception:
                pass

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
