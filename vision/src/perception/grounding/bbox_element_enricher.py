"""
Enrich refined bounding boxes with semantic element metadata using Gemini VLM.

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


def _is_interactive_type(elem_type: str) -> bool:
    t = str(elem_type or "").strip().lower()
    return t in {"button", "link", "input_field", "dropdown"}


def _infer_label_from_context(
    idx: int,
    entries: List[Dict[str, Any]],
    image_h: int,
) -> str:
    """
    Infer missing labels from nearby text context.
    - Prefer nearest text above/left of target.
    - Generic nearest-neighbor text association only.
    """
    if idx < 0 or idx >= len(entries):
        return ""

    cur = entries[idx]
    cx = float(cur.get("dx", 0))
    cy = float(cur.get("dy", 0))
    radius = max(8.0, 0.05 * float(image_h))

    candidates: List[Tuple[float, str]] = []
    for j, e in enumerate(entries):
        if j == idx:
            continue
        et = str(e.get("type", "unknown")).strip().lower()
        txt = " ".join(str(e.get("label", "")).split()).strip()
        if not txt:
            txt = " ".join(str(e.get("ocr_text", "")).split()).strip()
        if not txt:
            continue
        # standalone text-like elements only
        if et not in {"text", "label"}:
            continue
        ex = float(e.get("dx", 0))
        ey = float(e.get("dy", 0))
        dist = ((cx - ex) ** 2 + (cy - ey) ** 2) ** 0.5
        if dist <= radius:
            candidates.append((dist, txt))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1][:80]

    return ""


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

    # Generic role inference (geometry + visual texture only).
    if text_density > 0.24 and edge_density < 0.20:
        element_type = "text"
    elif area <= 2300 and 0.75 <= ar <= 1.35:
        element_type = "icon"
    elif ar >= 2.8 and h <= 130:
        element_type = "input_field" if edge_density < 0.15 else "button"
    elif 1.35 <= ar < 2.8 and h <= 120:
        element_type = "button"
    elif edge_density < 0.08 and area > 18000:
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
) -> None:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Failed to read image: {image_path}")
    h, w = image.shape[:2]

    with open(refined_bbox_path, "r", encoding="utf-8") as f:
        refined = json.load(f)
    boxes = refined.get("bboxes", [])

    max_vlm_calls = len(boxes)
    vlm_calls_used = 0

    staged: List[Dict[str, Any]] = []
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

        if not _safe_str(meta.get("label")).strip() and ocr_text:
            meta["label"] = ocr_text
        if not _safe_str(meta.get("description")).strip():
            meta["description"] = describe_ui_element(
                vlm_client=None,
                crop=crop,
                label=_safe_str(meta.get("label")),
                type_hint=_safe_str(meta.get("type", heuristic["type"])),
            )

        staged.append(
            {
                "id": f"elem_{idx}",
                "type": str(meta.get("type", "unknown")).strip().lower() or "unknown",
                "label": " ".join(str(meta.get("label", "")).split()).strip(),
                "description": str(meta.get("description", "")).strip(),
                "state": str(meta.get("state", "normal")).strip().lower() or "normal",
                "dx": int(item.get("dx", dx)),
                "dy": int(item.get("dy", dy)),
                "bbox": list(bbox),
                "dxdy": item.get("dxdy", []),
                "screen_bbox": item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0]),
                "ocr_text": ocr_text,
                "confidence": float(meta.get("confidence", 0.5)),
                "source": (
                    item.get("source", "ui_detector")
                    if str(item.get("source", "")).strip() == "vlm_discovery"
                    else ("ocr_enriched" if ocr_text else item.get("source", "ui_detector"))
                ),
            }
        )
    # Strict OCR/context label enforcement for interactive elements.
    elements: List[Dict[str, Any]] = []
    for i, e in enumerate(staged):
        et = str(e.get("type", "unknown")).strip().lower()
        lbl = " ".join(str(e.get("label", "")).split()).strip()
        ocr = " ".join(str(e.get("ocr_text", "")).split()).strip()
        if _is_interactive_type(et):
            if ocr:
                lbl = ocr
            elif not lbl:
                lbl = _infer_label_from_context(i, staged, image_h=h)
        else:
            if not lbl and ocr:
                lbl = ocr

        # No coordinate-based fallback labels.
        # Leave label empty when OCR/context cannot infer.

        desc = str(e.get("description", "")).strip()
        if not desc:
            # semantic fallback only, without coordinate-style labels
            desc = describe_ui_element(
                vlm_client=None,
                crop=image[
                    _to_pixel_bbox(tuple(e.get("bbox", [0, 0, 1, 1])), w, h)[1]:
                    _to_pixel_bbox(tuple(e.get("bbox", [0, 0, 1, 1])), w, h)[3],
                    _to_pixel_bbox(tuple(e.get("bbox", [0, 0, 1, 1])), w, h)[0]:
                    _to_pixel_bbox(tuple(e.get("bbox", [0, 0, 1, 1])), w, h)[2],
                ],
                label=lbl,
                type_hint=et,
            )

        out = dict(e)
        out["label"] = lbl
        out["description"] = desc
        out.pop("bbox", None)
        elements.append(out)

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
    parser.add_argument("--no-vlm", action="store_true", help="Skip VLM classification and output unknown types.")
    args = parser.parse_args()

    # Late import so script can still run with --no-vlm in limited envs.
    vlm_client = None
    if not args.no_vlm:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from perception.vlm import get_vlm_client
        vlm_client = get_vlm_client()

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
        )
        print(f"[BBoxEnricher] Wrote {out_path.name}")


if __name__ == "__main__":
    main()
