# src/perception/vlm/vlm_client.py
"""
VLM (Vision-Language Model) client for UI detection.
Supports Claude (Anthropic), GPT-4V (OpenAI), Ollama, and local VLMs.

Key design: classify_elements_batch() issues a SINGLE VLM call per frame,
sending the full image and all element bounding boxes together, which
eliminates per-element budget exhaustion.
"""

import os
import base64
import json
import hashlib
import logging
import time
from typing import Optional, List, Dict, Any, Tuple
from abc import ABC, abstractmethod
from urllib import request, error
import cv2
import numpy as np

from .ui_parser import UIElement, UIParser, UIAnalysisResult
from .prompt_templates import get_ui_discovery_prompt

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
                "required": ["id", "type", "label", "state", "confidence"],
                "properties": {
                    "id":         {"type": "string"},
                    "type":       {"type": "string"},
                    "label":      {"type": "string"},
                    "state":      {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
        }
    },
}

# Minimum fraction of total image area for an element to be sent to the VLM.
MIN_AREA_FRACTION = 0.01          # 1 %
# Maximum allowed aspect ratio (width/height or height/width).
MAX_ASPECT_RATIO  = 20.0


def _compute_frame_hash(image_path: str) -> str:
    """Return a SHA-256 hex digest of the raw image bytes."""
    h = hashlib.sha256()
    with open(image_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    """Return the area of a normalised (0-1) bounding box."""
    x_min, y_min, x_max, y_max = bbox
    return max(0.0, x_max - x_min) * max(0.0, y_max - y_min)


def _bbox_aspect_ratio(bbox: Tuple[float, float, float, float]) -> float:
    """Return the larger aspect ratio (always >= 1)."""
    w = max(1e-9, bbox[2] - bbox[0])
    h = max(1e-9, bbox[3] - bbox[1])
    ratio = w / h
    return max(ratio, 1.0 / ratio)


def _bbox_iou(b1: Tuple[float, float, float, float],
              b2: Tuple[float, float, float, float]) -> float:
    """Intersection-over-Union for two normalised bboxes."""
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
    iou_threshold: float = 0.7,
) -> List[UIElement]:
    """
    Greedily merge elements with IoU above *iou_threshold*.
    The element with the higher confidence is kept; the other is discarded.
    """
    if not elements:
        return []
    kept = sorted(elements, key=lambda e: e.confidence, reverse=True)
    out: List[UIElement] = []
    while kept:
        current = kept.pop(0)
        remaining: List[UIElement] = []
        for other in kept:
            if _bbox_iou(current.bbox, other.bbox) >= iou_threshold:
                # absorb: keep current (higher confidence), discard other
                pass
            else:
                remaining.append(other)
        out.append(current)
        kept = remaining
    return out


def _filter_elements_for_vlm(
    elements: List[UIElement],
) -> Tuple[List[UIElement], List[UIElement]]:
    """
    Partition elements into (to_classify, skipped).

    An element is skipped when:
      - Its normalised bbox area is < MIN_AREA_FRACTION  (too small)
      - Its aspect ratio exceeds MAX_ASPECT_RATIO         (extreme shape)
    """
    to_classify: List[UIElement] = []
    skipped:    List[UIElement] = []
    for elem in elements:
        area = _bbox_area(elem.bbox)
        ar   = _bbox_aspect_ratio(elem.bbox)
        if area < MIN_AREA_FRACTION or ar > MAX_ASPECT_RATIO:
            skipped.append(elem)
        else:
            to_classify.append(elem)
    return to_classify, skipped


def _validate_batch_response(data: Any) -> bool:
    """Lightweight JSON-schema validation for the batch response."""
    if not isinstance(data, dict):
        return False
    elements = data.get("elements")
    if not isinstance(elements, list):
        return False
    for item in elements:
        if not isinstance(item, dict):
            return False
        for key in ("id", "type", "label", "state", "confidence"):
            if key not in item:
                return False
        if not isinstance(item["confidence"], (int, float)):
            return False
    return True


def _fallback_classification(elements: List[UIElement]) -> List[Dict[str, Any]]:
    """
    Return stub classifications when the VLM is unavailable.
    Preserves original type when already set; otherwise uses 'unknown'.
    """
    result = []
    for elem in elements:
        result.append({
            "id":         elem.id,
            "type":       elem.type if elem.type not in ("", "unknown") else "unknown",
            "label":      elem.label or "",
            "state":      elem.state or "normal",
            "confidence": elem.confidence if elem.type != "unknown" else 0.1,
        })
    return result


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class VLMClient(ABC):
    """Abstract base class for VLM clients."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = ""):
        self.api_key  = api_key
        self.model_name = model_name
        self.parser   = UIParser()
        # in-memory cache: frame_hash -> List[Dict] (batch classification result)
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    @abstractmethod
    def analyze_ui(self, image_path: str, prompt: Optional[str] = None,
                   **kwargs) -> UIAnalysisResult:
        """Full-image UI analysis (zero-shot discovery)."""
        pass

    # ------------------------------------------------------------------
    # Single-call batch classification  (ISSUE 1 fix)
    # ------------------------------------------------------------------

    def classify_elements_batch(
        self,
        image_path: str,
        elements: List[UIElement],
        max_retries: int = 2,
        timeout_seconds: float = 60.0,
    ) -> List[UIElement]:
        """
        Classify *all* detected elements in ONE VLM call.

        Workflow
        --------
        1. Hash image â†’ check in-memory cache.
        2. Filter tiny / extreme-AR elements.
        3. Merge heavily overlapping boxes.
        4. Build a structured prompt with all element IDs + bboxes.
        5. Call VLM once; retry up to *max_retries* on failure.
        6. Validate JSON response against schema.
        7. Merge classifications back onto original element list.
        8. Cache result keyed by frame hash.

        Returns the input element list with updated type/label/state/confidence.
        """
        if not elements:
            return elements

        frame_hash = _compute_frame_hash(image_path)

        # --- cache hit ---
        if frame_hash in self._cache:
            logger.debug("classify_elements_batch: cache hit for %s", image_path)
            cached = self._cache[frame_hash]
            return self._apply_classifications(elements, cached)

        # --- filter ---
        to_classify, skipped = _filter_elements_for_vlm(elements)
        # merge overlapping before sending to VLM
        to_classify = _merge_overlapping_elements(to_classify)

        if not to_classify:
            logger.debug("classify_elements_batch: all elements filtered; using fallback")
            return self._apply_classifications(
                elements, _fallback_classification(elements)
            )

        # --- build prompt ---
        element_list_json = json.dumps(
            [{"id": e.id, "bbox": list(e.bbox)} for e in to_classify],
            indent=2,
        )
        prompt = (
            "You are a precise UI element classifier.\n\n"
            "You are given a screenshot and a list of UI elements with their bounding boxes "
            "(normalised to 0-1 range: [x_min, y_min, x_max, y_max]).\n\n"
            "For EVERY element in the list classify it and return ONLY valid JSON with this exact schema:\n"
            "{\n"
            '  "elements": [\n'
            "    {\n"
            '      "id": "<same id as input>",\n'
            '      "type": "<button|input_field|text|label|icon|dropdown|checkbox|radio|menu|tab|link|card|list_item|image|unknown>",\n'
            '      "label": "<short visible text or description>",\n'
            '      "state": "<enabled|disabled|focused|checked|unchecked|normal>",\n'
            '      "confidence": <0.0-1.0>\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Elements to classify:\n"
            f"{element_list_json}\n\n"
            "Rules:\n"
            "1. Return ONLY the JSON object â€“ no prose, no markdown fences.\n"
            "2. Include every element id from the input list.\n"
            "3. confidence reflects how certain you are about the type.\n"
        )

        # --- retry loop ---
        raw_classifications: Optional[List[Dict[str, Any]]] = None
        last_error: str = ""
        for attempt in range(max_retries + 1):
            try:
                raw_classifications = self._do_batch_classify(
                    image_path, prompt, timeout_seconds
                )
                if raw_classifications is not None:
                    break
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "classify_elements_batch attempt %d/%d failed: %s",
                    attempt + 1, max_retries + 1, last_error,
                )
                if attempt < max_retries:
                    time.sleep(1.0 * (attempt + 1))

        if raw_classifications is None:
            logger.error(
                "classify_elements_batch: all attempts failed (%s); using fallback", last_error
            )
            raw_classifications = _fallback_classification(to_classify)

        # incorporate skipped elements (fallback classification)
        raw_classifications.extend(_fallback_classification(skipped))

        # cache result
        self._cache[frame_hash] = raw_classifications

        return self._apply_classifications(elements, raw_classifications)

    def _do_batch_classify(
        self,
        image_path: str,
        prompt: str,
        timeout_seconds: float,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Subclasses implement this to perform the actual VLM call.
        Must return a list of classification dicts or raise on failure.
        Default implementation raises NotImplementedError so subclasses can
        opt-in.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement _do_batch_classify; "
            "single-call batch classification is unavailable."
        )

    @staticmethod
    def _apply_classifications(
        elements: List[UIElement],
        classifications: List[Dict[str, Any]],
    ) -> List[UIElement]:
        """Merge classification results back onto the UIElement list."""
        id_map: Dict[str, Dict[str, Any]] = {c["id"]: c for c in classifications}
        for elem in elements:
            cls = id_map.get(elem.id)
            if cls:
                elem.type        = cls.get("type",       elem.type)
                elem.label       = cls.get("label",      elem.label)
                elem.state       = cls.get("state",      elem.state)
                elem.confidence  = float(cls.get("confidence", elem.confidence))
        return elements

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image file to base64 string."""
        with open(image_path, "rb") as fh:
            return base64.standard_b64encode(fh.read()).decode("utf-8")

    def encode_numpy_to_base64(self, image_array: np.ndarray, fmt: str = ".jpg") -> str:
        """Encode numpy array to base64 string."""
        success, buffer = cv2.imencode(fmt, image_array)
        if not success:
            raise ValueError("Failed to encode image")
        return base64.standard_b64encode(buffer).decode("utf-8")

    def get_image_dimensions(self, image_path: str) -> Tuple[Optional[int], Optional[int]]:
        """Return (width, height) for the image, or (None, None) on failure."""
        img = cv2.imread(image_path)
        if img is None:
            return None, None
        height, width = img.shape[:2]
        return width, height


class ClaudeVLMClient(VLMClient):
    """Claude (Anthropic) Vision API client."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key or os.getenv("ANTHROPIC_API_KEY"), model_name)
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def _claude_vision_call(self, image_path: str, prompt: str) -> str:
        """Send a vision prompt to Claude and return the text content."""
        image_data = self.encode_image_to_base64(image_path)
        message = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return message.content[0].text

    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, **kwargs) -> UIAnalysisResult:
        """Analyze UI using Claude Vision API."""
        prompt = prompt or get_ui_discovery_prompt()
        try:
            width, height = self.get_image_dimensions(image_path)
            response_text = self._claude_vision_call(image_path, prompt)
            return self.parser.parse_vlm_response(response_text, width, height)
        except Exception as exc:
            return UIAnalysisResult(elements=[], parse_successful=False,
                                    parse_error=f"Claude API error: {exc}")

    def _do_batch_classify(self, image_path: str, prompt: str, timeout_seconds: float) -> Optional[List[Dict[str, Any]]]:
        """Single-call batch classification via Claude."""
        response_text = self._claude_vision_call(image_path, prompt)
        data = self.parser.extract_json_from_response(response_text)
        if not _validate_batch_response(data):
            raise ValueError("Claude batch response failed schema validation")
        return data["elements"]


class GPT4VClient(VLMClient):
    """GPT-4V (OpenAI) Vision API client."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4-vision-preview"):
        super().__init__(api_key or os.getenv("OPENAI_API_KEY"), model_name)
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def _gpt4v_call(self, image_path: str, prompt: str) -> str:
        """Send a vision prompt to GPT-4V and return the text content."""
        image_data = self.encode_image_to_base64(image_path)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=4096,
        )
        return response.choices[0].message.content

    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, **kwargs) -> UIAnalysisResult:
        """Analyze UI using GPT-4V API."""
        prompt = prompt or get_ui_discovery_prompt()
        try:
            width, height = self.get_image_dimensions(image_path)
            response_text = self._gpt4v_call(image_path, prompt)
            return self.parser.parse_vlm_response(response_text, width, height)
        except Exception as exc:
            return UIAnalysisResult(elements=[], parse_successful=False,
                                    parse_error=f"GPT-4V API error: {exc}")

    def _do_batch_classify(self, image_path: str, prompt: str, timeout_seconds: float) -> Optional[List[Dict[str, Any]]]:
        """Single-call batch classification via GPT-4V."""
        response_text = self._gpt4v_call(image_path, prompt)
        data = self.parser.extract_json_from_response(response_text)
        if not _validate_batch_response(data):
            raise ValueError("GPT-4V batch response failed schema validation")
        return data["elements"]


class LocalVLMClient(VLMClient):
    """Local VLM client using open-source models (e.g., LLaVA, Qwen)."""

    def __init__(self, model_name: str = "llava-hf/llava-1.5-7b-hf"):
        super().__init__(None, model_name)
        try:
            from transformers import AutoProcessor, AutoModelForCausalLM
            import torch

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.processor = AutoProcessor.from_pretrained(model_name)
            dtype = torch.float16 if self.device == "cuda" else torch.float32

            try:
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name, torch_dtype=dtype, device_map="auto"
                )
            except Exception:
                try:
                    from transformers import AutoModelForVision2Seq
                    self.model = AutoModelForVision2Seq.from_pretrained(
                        model_name, torch_dtype=dtype, device_map="auto"
                    )
                except Exception:
                    from transformers import LlavaForConditionalGeneration
                    self.model = LlavaForConditionalGeneration.from_pretrained(
                        model_name, torch_dtype=dtype, device_map="auto"
                    )
        except ImportError:
            raise ImportError(
                "transformers/torch not installed. Run: "
                "pip install torch torchvision transformers sentencepiece accelerate"
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to initialise local model '{model_name}': {exc}")

    def _local_generate(self, image_path: str, prompt: str) -> str:
        """Run local model inference and return response text."""
        from PIL import Image
        import torch

        image = Image.open(image_path).convert("RGB")
        if "llava" in self.model_name.lower() and "<image>" not in prompt:
            prompt = f"<image>\n{prompt}"
        inputs = self.processor(text=prompt, images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            output_ids = self.model.generate(**inputs, max_new_tokens=2048)
        text = self.processor.decode(output_ids[0], skip_special_tokens=True)
        return text.replace(prompt, "").strip()

    def analyze_ui(self, image_path: str, prompt: Optional[str] = None, **kwargs) -> UIAnalysisResult:
        """Analyze UI using local VLM."""
        prompt = prompt or get_ui_discovery_prompt()
        try:
            from PIL import Image
            width, height = Image.open(image_path).size
            response_text = self._local_generate(image_path, prompt)
            return self.parser.parse_vlm_response(response_text, width, height)
        except Exception as exc:
            return UIAnalysisResult(elements=[], parse_successful=False,
                                    parse_error=f"Local VLM error: {exc}")

    def _do_batch_classify(self, image_path: str, prompt: str, timeout_seconds: float) -> Optional[List[Dict[str, Any]]]:
        """Single-call batch classification via local model."""
        response_text = self._local_generate(image_path, prompt)
        data = self.parser.extract_json_from_response(response_text)
        if not _validate_batch_response(data):
            raise ValueError("Local VLM batch response failed schema validation")
        return data["elements"]


def get_vlm_client(provider: str = "claude", **kwargs) -> VLMClient:
    """
    Factory function to create a VLM client.

    Args:
        provider: One of ``"claude"``, ``"gpt4v"``, ``"openai"``, ``"local"``, ``"ollama"``.
        **kwargs: Provider-specific init arguments.

    Returns:
        VLMClient instance.
    """
    provider = provider.lower().strip()
    if provider == "claude":
        return ClaudeVLMClient(**kwargs)
    elif provider in ("gpt4v", "openai", "gpt-4v"):
        return GPT4VClient(**kwargs)
    elif provider == "local":
        return LocalVLMClient(**kwargs)
    elif provider == "ollama":
        return OllamaVLMClient(**kwargs)
    else:
        raise ValueError(f"Unknown VLM provider: {provider!r}")
