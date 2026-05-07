"""Gemini-only VLM client for UI detection."""

import base64
import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .prompt_templates import get_ui_discovery_prompt
from .ui_parser import UIAnalysisResult, UIElement, UIParser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema for batch classification response
# ---------------------------------------------------------------------------
BATCH_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["elements"],
    "properties": {
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type", "label", "description", "state", "confidence"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "state": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
        }
    },
}

# Minimum fraction of total image area for an element to be sent to the VLM.
MIN_AREA_FRACTION = 0.00035
# Maximum allowed aspect ratio (width/height or height/width).
MAX_ASPECT_RATIO = 28.0


def _compute_frame_hash(image_path: str) -> str:
    h = hashlib.sha256()
    with open(image_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    x_min, y_min, x_max, y_max = bbox
    return max(0.0, x_max - x_min) * max(0.0, y_max - y_min)


def _bbox_aspect_ratio(bbox: Tuple[float, float, float, float]) -> float:
    w = max(1e-9, bbox[2] - bbox[0])
    h = max(1e-9, bbox[3] - bbox[1])
    ratio = w / h
    return max(ratio, 1.0 / ratio)


def _bbox_iou(
    b1: Tuple[float, float, float, float],
    b2: Tuple[float, float, float, float],
) -> float:
    x1, y1 = max(b1[0], b2[0]), max(b1[1], b2[1])
    x2, y2 = min(b1[2], b2[2]), min(b1[3], b2[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    a1 = _bbox_area(b1)
    a2 = _bbox_area(b2)
    denom = a1 + a2 - inter
    return inter / denom if denom > 0 else 0.0


def _merge_overlapping_elements(
    elements: List[UIElement],
    iou_threshold: float = 0.58,
) -> List[UIElement]:
    if not elements:
        return []
    kept = sorted(elements, key=lambda e: e.confidence, reverse=True)
    out: List[UIElement] = []
    while kept:
        current = kept.pop(0)
        remaining: List[UIElement] = []
        for other in kept:
            if _bbox_iou(current.bbox, other.bbox) >= iou_threshold:
                continue
            remaining.append(other)
        out.append(current)
        kept = remaining
    return out


def _filter_elements_for_vlm(
    elements: List[UIElement],
) -> Tuple[List[UIElement], List[UIElement]]:
    to_classify: List[UIElement] = []
    skipped: List[UIElement] = []
    for elem in elements:
        area = _bbox_area(elem.bbox)
        ar = _bbox_aspect_ratio(elem.bbox)
        raw = elem.raw_data if isinstance(elem.raw_data, dict) else {}
        source = str(raw.get("source", "")).lower()
        if source == "layout_text":
            min_area = MIN_AREA_FRACTION * 0.25
            max_ar = MAX_ASPECT_RATIO * 1.6
        elif source == "layout_form":
            min_area = MIN_AREA_FRACTION * 0.6
            max_ar = MAX_ASPECT_RATIO * 1.35
        elif source == "layout_adaptive":
            min_area = MIN_AREA_FRACTION * 1.25
            max_ar = MAX_ASPECT_RATIO
        else:
            min_area = MIN_AREA_FRACTION
            max_ar = MAX_ASPECT_RATIO
        if area < min_area or ar > max_ar:
            skipped.append(elem)
        else:
            to_classify.append(elem)
    return to_classify, skipped


def _validate_batch_response(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    elements = data.get("elements")
    if not isinstance(elements, list):
        return False
    for item in elements:
        if not isinstance(item, dict):
            return False
        for key in ("id", "type", "label", "description", "state", "confidence"):
            if key not in item:
                return False
        if not isinstance(item["confidence"], (int, float)):
            return False
        if not str(item.get("description", "")).strip():
            return False
    return True


def _fallback_classification(elements: List[UIElement]) -> List[Dict[str, Any]]:
    def _clean_label(label: str) -> str:
        return " ".join(str(label).strip().split())

    def _human_type(elem_type: str) -> str:
        return str(elem_type).replace("_", " ").strip()

    def _infer_type(elem: UIElement) -> str:
        existing = (elem.type or "").strip().lower()
        if existing and existing != "unknown":
            return existing
        raw = elem.raw_data if isinstance(elem.raw_data, dict) else {}
        source = str(raw.get("source", "")).lower()
        x1, y1, x2, y2 = elem.bbox
        bw = max(1e-9, x2 - x1)
        bh = max(1e-9, y2 - y1)
        ar = bw / bh
        area = bw * bh
        if source == "layout_text":
            return "text"
        if source == "layout_form":
            return "input_field" if ar >= 2.0 else "button"
        if source == "layout_edge" and area >= 0.12:
            return "image"
        if ar >= 3.0 and bh <= 0.16:
            return "input_field"
        if ar >= 1.4 and bh <= 0.20:
            return "button"
        if area <= 0.0025:
            return "icon"
        return "text"

    def _infer_state(elem_type: str, current: str) -> str:
        state = (current or "").strip().lower()
        if state and state != "unknown":
            return state
        if elem_type == "checkbox":
            return "unchecked"
        return "normal"

    def _infer_label(elem: UIElement, elem_type: str) -> str:
        label = _clean_label(elem.label)
        if label:
            return label
        raw = elem.raw_data if isinstance(elem.raw_data, dict) else {}
        ocr = _clean_label(str(raw.get("ocr_text", "")))
        if ocr:
            return ocr
        human = _human_type(elem_type)
        if human == "input field":
            return "Input field"
        if human == "button":
            return "Button"
        if human == "link":
            return "Link"
        return human.capitalize()

    def _infer_description(elem: UIElement, elem_type: str, label: str) -> str:
        desc = str(elem.description or "").strip()
        if desc and desc not in VLMClient._STALE_DESCRIPTIONS:
            return desc
        raw = elem.raw_data if isinstance(elem.raw_data, dict) else {}
        dx = raw.get("dx", "")
        dy = raw.get("dy", "")
        pos = ""
        try:
            pos = f" at ({int(round(float(dx)))},{int(round(float(dy)))})"
        except Exception:
            pos = ""
        if label:
            return f"{_human_type(elem_type).capitalize()} labeled '{label}'{pos}, likely used for interaction."
        return f"{_human_type(elem_type).capitalize()} in the interface{pos}, likely part of the workflow."

    result = []
    for elem in elements:
        inferred_type = _infer_type(elem)
        inferred_label = _infer_label(elem, inferred_type)
        inferred_desc = _infer_description(elem, inferred_type, inferred_label)
        inferred_state = _infer_state(inferred_type, elem.state)
        result.append(
            {
                "id": elem.id,
                "type": inferred_type,
                "label": inferred_label,
                "description": inferred_desc,
                "state": inferred_state,
                "confidence": max(0.2, float(elem.confidence or 0.0)),
            }
        )
    return result


class VLMClient(ABC):
    """Abstract base class for Gemini-backed VLM clients."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = ""):
        self.api_key = api_key
        self.model_name = model_name
        self.parser = UIParser()
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    @abstractmethod
    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, **kwargs) -> UIAnalysisResult:
        raise NotImplementedError

    def classify_elements_batch(
        self,
        image_path: str,
        elements: List[UIElement],
        max_retries: int = 2,
        timeout_seconds: float = 60.0,
    ) -> List[UIElement]:
        if not elements:
            return elements

        frame_hash = _compute_frame_hash(image_path)
        if frame_hash in self._cache:
            logger.debug("classify_elements_batch: cache hit for %s", image_path)
            return self._apply_classifications(elements, self._cache[frame_hash])

        to_classify, skipped = _filter_elements_for_vlm(elements)
        to_classify = _merge_overlapping_elements(to_classify)

        if not to_classify:
            logger.debug("classify_elements_batch: all elements filtered; using fallback")
            return self._apply_classifications(elements, _fallback_classification(elements))

        element_payload: List[Dict[str, Any]] = []
        for e in to_classify:
            raw = e.raw_data if isinstance(e.raw_data, dict) else {}
            element_payload.append(
                {
                    "id": e.id,
                    "bbox": [float(v) for v in e.bbox],
                    "hint_type": str(e.type or "").strip(),
                    "hint_label": " ".join(str(e.label or "").split()).strip(),
                    "ocr_text": " ".join(str(raw.get("ocr_text", "")).split()).strip(),
                    "source": str(raw.get("source", "")),
                    "dx": raw.get("dx"),
                    "dy": raw.get("dy"),
                }
            )

        element_list_json = json.dumps(element_payload, indent=2)
        prompt = (
            "You are an expert UI element classifier for automation.\n\n"
            "You are given ONE screenshot and a list of UI element candidates with bboxes.\n"
            "Classify every candidate using the screenshot content and each candidate bbox.\n"
            "Do not skip any element id.\n\n"
            "For EVERY element in the list classify it and return ONLY valid JSON with this exact schema:\n"
            "{\n"
            '  "elements": [\n'
            "    {\n"
            '      "id": "<same id as input>",\n'
            '      "type": "<button|input_field|text|label|icon|dropdown|checkbox|radio|menu|tab|link|card|list_item|image|unknown>",\n'
            '      "label": "<short visible text or functional name; never empty>",\n'
            '      "description": "<one sentence describing what this element does or shows>",\n'
            '      "state": "<enabled|disabled|focused|checked|unchecked|normal>",\n'
            '      "confidence": <0.0-1.0>\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Elements to classify:\n"
            f"{element_list_json}\n\n"
            "Rules:\n"
            "1. Return ONLY the JSON object - no prose, no markdown fences.\n"
            "2. Include every element id from the input list.\n"
            "3. Never leave label or description empty.\n"
            "4. If no readable text, create a concise functional label (example: 'menu icon', 'submit button', 'table row').\n"
            "5. Avoid type='unknown' unless the element has no discernible UI role.\n"
            "6. Use hint_type/hint_label/ocr_text as soft hints, not strict truth.\n"
            "7. Keep labels short (2-6 words).\n"
            "8. state must never be unknown; use normal when uncertain.\n"
            "9. confidence reflects certainty of type classification.\n"
            "10. description should be specific and concrete, not generic boilerplate.\n"
        )

        raw_classifications: Optional[List[Dict[str, Any]]] = None
        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                raw_classifications = self._do_batch_classify(image_path, prompt, timeout_seconds)
                if raw_classifications is not None:
                    break
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "classify_elements_batch attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    last_error,
                )
                if attempt < max_retries:
                    time.sleep(1.0 * (attempt + 1))

        if raw_classifications is None:
            logger.error(
                "classify_elements_batch: all attempts failed (%s); using fallback",
                last_error,
            )
            raw_classifications = _fallback_classification(to_classify)

        raw_classifications.extend(_fallback_classification(skipped))
        self._cache[frame_hash] = raw_classifications
        return self._apply_classifications(elements, raw_classifications)

    def _do_batch_classify(
        self,
        image_path: str,
        prompt: str,
        timeout_seconds: float,
    ) -> Optional[List[Dict[str, Any]]]:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement _do_batch_classify; batch classification is unavailable."
        )

    _STALE_DESCRIPTIONS: frozenset = frozenset({
        "No VLM available",
        "VLM classification failed",
        "Skipped VLM classification (provider budget)",
    })

    @staticmethod
    def _apply_classifications(
        elements: List[UIElement],
        classifications: List[Dict[str, Any]],
    ) -> List[UIElement]:
        valid_types = {
            "button",
            "input_field",
            "text",
            "label",
            "icon",
            "dropdown",
            "checkbox",
            "radio",
            "menu",
            "tab",
            "link",
            "card",
            "list_item",
            "image",
        }
        id_map: Dict[str, Dict[str, Any]] = {c["id"]: c for c in classifications}
        stale = VLMClient._STALE_DESCRIPTIONS
        for elem in elements:
            cls = id_map.get(elem.id)
            if cls:
                if not isinstance(elem.raw_data, dict):
                    elem.raw_data = {}
                cls_type = str(cls.get("type", elem.type or "")).strip().lower()
                if cls_type and cls_type in valid_types:
                    elem.type = cls_type
                cls_label = " ".join(str(cls.get("label", elem.label or "")).split()).strip()
                if cls_label:
                    elem.label = cls_label
                cls_state = str(cls.get("state", elem.state or "")).strip().lower()
                elem.state = cls_state if cls_state and cls_state != "unknown" else "normal"
                elem.confidence = float(cls.get("confidence", elem.confidence))
                vlm_desc = str(cls.get("description", "")).strip()
                if vlm_desc:
                    elem.description = vlm_desc
                elif elem.description in stale:
                    elem.description = ""
                elem.raw_data["source"] = "gemini_enriched"
            if not elem.type or elem.type == "unknown":
                elem.type = "text"
            elem.label = " ".join(str(elem.label or "").split()).strip()
            if not elem.label:
                human = elem.type.replace("_", " ").strip()
                if human == "input field":
                    elem.label = "Input field"
                elif human == "button":
                    elem.label = "Button"
                elif human == "link":
                    elem.label = "Link"
                else:
                    elem.label = human.capitalize()
            if not str(elem.description).strip() or elem.description in stale:
                if elem.label:
                    elem.description = (
                        f"{elem.type.replace('_', ' ').capitalize()} labeled '{elem.label}', identified in the current screen context."
                    )
                else:
                    elem.description = (
                        f"{elem.type.replace('_', ' ').capitalize()} identified in the current screen context."
                    )
            if not str(elem.state).strip() or elem.state == "unknown":
                elem.state = "normal"
            elem.confidence = max(0.1, min(1.0, float(elem.confidence)))
        return elements

    def encode_image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as fh:
            return base64.standard_b64encode(fh.read()).decode("utf-8")

    def encode_numpy_to_base64(self, image_array: np.ndarray, fmt: str = ".jpg") -> str:
        success, buffer = cv2.imencode(fmt, image_array)
        if not success:
            raise ValueError("Failed to encode image")
        return base64.standard_b64encode(buffer).decode("utf-8")

    def get_image_dimensions(self, image_path: str) -> Tuple[Optional[int], Optional[int]]:
        img = cv2.imread(image_path)
        if img is None:
            return None, None
        height, width = img.shape[:2]
        return width, height


class GeminiVLMClient(VLMClient):
    """Gemini Vision API client."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-flash-latest"):
        super().__init__(api_key or os.getenv("GEMINI_API_KEY"), model_name)
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")
        try:
            import google.generativeai as genai
            self._genai = genai
            self._genai.configure(api_key=self.api_key)
            self.model_name = self._resolve_model_name(self.model_name)
            self.client = self._genai.GenerativeModel(self.model_name)
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. Run: pip install google-generativeai"
            )

    def _resolve_model_name(self, requested_model: str) -> str:
        try:
            models = list(self._genai.list_models())
            supported: List[str] = []
            for model in models:
                methods = set(getattr(model, "supported_generation_methods", []) or [])
                if "generateContent" in methods:
                    name = str(getattr(model, "name", ""))
                    if name.startswith("models/"):
                        name = name.split("/", 1)[1]
                    if name:
                        supported.append(name)
            if not supported:
                return requested_model
            if requested_model in supported:
                return requested_model
            preferred = [
                "gemini-flash-latest",
                "gemini-flash-lite-latest",
                "gemini-pro-latest",
                "gemini-2.5-flash",
                "gemini-2.0-flash-lite",
                "gemini-2.0-flash",
            ]
            for candidate in preferred:
                if candidate in supported:
                    logger.warning("Requested Gemini model '%s' unavailable; using '%s'", requested_model, candidate)
                    return candidate
            for candidate in supported:
                if candidate.startswith("gemini-"):
                    logger.warning("Requested Gemini model '%s' unavailable; using '%s'", requested_model, candidate)
                    return candidate
            return requested_model
        except Exception as exc:
            logger.warning("Could not list Gemini models, using requested model '%s': %s", requested_model, exc)
            return requested_model

    def _gemini_vision_call(self, image_path: str, prompt: str, timeout_seconds: float = 60.0) -> str:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        payload = [
            {"mime_type": "image/jpeg", "data": image_bytes},
            prompt,
        ]
        generation_config = {
            "temperature": 0,
            "max_output_tokens": 4096,
            "response_mime_type": "application/json",
        }
        request_options = {"timeout": int(max(1.0, timeout_seconds))}

        try:
            response = self.client.generate_content(
                payload,
                generation_config=generation_config,
                request_options=request_options,
            )
        except Exception as exc:
            msg = str(exc).lower()
            if "not found" in msg or "generatecontent" in msg:
                fallback = self._resolve_model_name(self.model_name)
                if fallback != self.model_name:
                    logger.warning("Retrying Gemini call with fallback model '%s'", fallback)
                    self.model_name = fallback
                    self.client = self._genai.GenerativeModel(self.model_name)
                    response = self.client.generate_content(
                        payload,
                        generation_config=generation_config,
                        request_options=request_options,
                    )
                else:
                    raise
            else:
                raise
        text = getattr(response, "text", "")
        if isinstance(text, str):
            return text
        return str(text)

    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, **kwargs) -> UIAnalysisResult:
        prompt = prompt or get_ui_discovery_prompt()
        try:
            width, height = self.get_image_dimensions(image_path)
            timeout_seconds = float(kwargs.get("timeout_seconds", 60.0))
            response_text = self._gemini_vision_call(image_path, prompt, timeout_seconds=timeout_seconds)
            result = self.parser.parse_vlm_response(response_text, width, height)
            if (not result.parse_successful or not result.elements) and "parse" in str(result.parse_error or "").lower():
                retry_prompt = (
                    get_ui_discovery_prompt()
                    + "\n\nIMPORTANT: Return strict JSON only. Keep descriptions short and do not add prose."
                )
                retry_text = self._gemini_vision_call(image_path, retry_prompt, timeout_seconds=timeout_seconds)
                retry_result = self.parser.parse_vlm_response(retry_text, width, height)
                if retry_result.elements:
                    return retry_result
                return retry_result
            return result
        except Exception as exc:
            return UIAnalysisResult(elements=[], parse_successful=False, parse_error=f"Gemini API error: {exc}")

    def _do_batch_classify(self, image_path: str, prompt: str, timeout_seconds: float) -> Optional[List[Dict[str, Any]]]:
        response_text = self._gemini_vision_call(image_path, prompt, timeout_seconds=timeout_seconds)
        data = self.parser.extract_json_from_response(response_text)
        if not _validate_batch_response(data):
            retry_prompt = prompt + "\n\nIMPORTANT: Return strict JSON only and do not truncate the elements list."
            retry_text = self._gemini_vision_call(image_path, retry_prompt, timeout_seconds=timeout_seconds)
            data = self.parser.extract_json_from_response(retry_text)
            if not _validate_batch_response(data):
                raise ValueError("Gemini batch response failed schema validation")
        return data["elements"]


def get_vlm_client(provider: str = "gemini", **kwargs) -> VLMClient:
    provider = provider.lower().strip()
    if provider != "gemini":
        raise ValueError(f"Unsupported VLM provider: {provider!r}. Gemini is the only supported provider.")
    return GeminiVLMClient(**kwargs)
