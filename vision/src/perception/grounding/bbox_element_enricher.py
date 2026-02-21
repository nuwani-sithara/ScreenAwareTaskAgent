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
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple

import cv2


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


def _classify_crop_with_vlm(vlm_client, crop_path: str) -> Dict[str, Any]:
    """
    Ask VLM to classify one cropped UI region.
    Returns fallback values on parse/model failure.
    """
    prompt = (
        "You are classifying a single cropped UI element.\n"
        "Return ONLY valid JSON in this exact schema:\n"
        "{\"elements\":[{\"id\":\"elem_0\",\"type\":\"button|input_field|text|label|icon|dropdown|checkbox|radio|menu|tab|modal|dialog|link|card|list_item|image|unknown\",\"label\":\"...\",\"description\":\"...\",\"state\":\"normal|active|disabled|focused|selected|unknown\",\"bbox\":[0,0,1,1],\"confidence\":0.0}]}\n"
        "Rules: return exactly one element; if unsure use type=unknown."
    )
    result = vlm_client.analyze_ui(crop_path, prompt=prompt)
    if not result.parse_successful or not result.elements:
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

    # Ollama can be too slow when called once per box on dense UIs.
    # Keep a small call budget and short timeout so final JSON is always emitted.
    is_ollama_client = (
        vlm_client is not None and vlm_client.__class__.__name__ == "OllamaVLMClient"
    )
    original_timeout = None
    if is_ollama_client and hasattr(vlm_client, "timeout_seconds"):
        try:
            original_timeout = float(vlm_client.timeout_seconds)
            vlm_client.timeout_seconds = min(original_timeout, 12.0)
        except Exception:
            original_timeout = None
    max_vlm_calls = 3 if is_ollama_client else len(boxes)
    vlm_calls_used = 0

    elements: List[Dict[str, Any]] = []
    try:
        for idx, item in enumerate(boxes):
            bbox = tuple(item.get("bbox", [0, 0, 1, 1]))
            x1, y1, x2, y2 = _to_pixel_bbox(bbox, w, h)
            crop = image[y1:y2, x1:x2]

            meta = {
                "type": "unknown",
                "label": "",
                "description": "No VLM available",
                "state": "unknown",
                "confidence": float(item.get("confidence", 0.5)),
            }

            should_call_vlm = (
                vlm_client is not None and crop.size > 0 and vlm_calls_used < max_vlm_calls
            )
            if should_call_vlm:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    crop_path = tmp.name
                try:
                    cv2.imwrite(crop_path, crop)
                    meta = _classify_crop_with_vlm(vlm_client, crop_path)
                except Exception:
                    meta = {
                        "type": "unknown",
                        "label": "",
                        "description": "VLM classification failed",
                        "state": "unknown",
                        "confidence": 0.1,
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
                    "bbox": list(bbox),
                    "confidence": meta["confidence"],
                    "source": item.get("source", "refined_bbox"),
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
        enrich_frame(image_path, f, out_path, vlm_client=vlm_client)
        print(f"[BBoxEnricher] Wrote {out_path.name}")


if __name__ == "__main__":
    main()
