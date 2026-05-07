"""Gemini powered semantic VLM implementation for screen-aware agents."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import warnings
from typing import Any, Dict, List

import cv2

from src.perception.grounding.coarse_bbox_generator import detect_screen_bbox
from src.vision.config import GEMINI_API_KEY, MODEL_NAME
from src.vision.vlm.base_vlm import BaseVLM

logger = logging.getLogger(__name__)
warnings.simplefilter("ignore", FutureWarning)


class GeminiVLM(BaseVLM):
    """Semantic VLM adapter using Gemini."""

    @staticmethod
    def _is_screenshot_mode() -> bool:
        mode = os.getenv("VISION_MODE", "").strip().lower()
        if mode in {"vision2", "vision_2", "v2"}:
            return True
        flag = os.getenv("VISION_SCREENSHOT_MODE", "0").strip().lower()
        return flag in {"1", "true", "yes", "on"}

    def __init__(self, model_name: str = MODEL_NAME, timeout_seconds: float = 45.0) -> None:
        self.model_name = model_name
        self.timeout_seconds = float(timeout_seconds)

        if not GEMINI_API_KEY:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. Set it in .env or export it before using provider=gemini."
            )

        try:
            warnings.filterwarnings(
                "ignore",
                category=FutureWarning,
                message=r".*google\.generativeai.*",
            )
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError(
                "google-generativeai package not installed. Run: pip install google-generativeai"
            ) from exc

        self._genai = genai
        self._genai.configure(api_key=GEMINI_API_KEY)
        self.model_name = self._resolve_model_name(self.model_name)
        self.client = self._genai.GenerativeModel(self.model_name)
        logger.info(
            "Initialized GeminiVLM model=%s timeout_seconds=%.1f",
            self.model_name,
            self.timeout_seconds,
        )

    def _resolve_model_name(self, requested_model: str) -> str:
        """Pick a generateContent-capable Gemini model, preferring the requested one."""
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
                logger.info("Gemini model listing returned no generateContent-capable models")
                return requested_model

            if requested_model in supported:
                return requested_model

            preferred = [
                "gemini-2.0-flash-lite",
                "gemini-2.0-flash",
                "gemini-flash-lite-latest",
                "gemini-flash-latest",
                "gemini-2.5-flash",
                "gemini-pro-latest",
            ]
            for candidate in preferred:
                if candidate in supported:
                    logger.warning(
                        "Requested Gemini model '%s' unavailable; using '%s'",
                        requested_model,
                        candidate,
                    )
                    return candidate

            for candidate in supported:
                if candidate.startswith("gemini-"):
                    logger.warning(
                        "Requested Gemini model '%s' unavailable; using '%s'",
                        requested_model,
                        candidate,
                    )
                    return candidate

            return requested_model
        except Exception as exc:
            logger.warning(
                "Could not list Gemini models, using requested model '%s': %s",
                requested_model,
                exc,
            )
            return requested_model

    @staticmethod
    def _safe_empty_response(
        image_path: str,
        image_width: int,
        image_height: int,
        vlm_error_type: str = "",
        vlm_error: str = "",
        vlm_retry_after_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "image": image_path,
            "image_size": {"width": int(image_width), "height": int(image_height)},
            "screen_bbox": [0, 0, int(image_width), int(image_height)],
            "screen_size": {"width": int(image_width), "height": int(image_height)},
            "coordinate_system": "pixel",
            "element_count": 0,
            "elements": [],
        }
        if vlm_error_type:
            payload["_vlm_error_type"] = vlm_error_type
        if vlm_error:
            payload["_vlm_error"] = vlm_error
        if vlm_retry_after_seconds > 0:
            payload["_vlm_retry_after_seconds"] = float(vlm_retry_after_seconds)
        return payload

    @staticmethod
    def _extract_retry_after_seconds(error_message: str) -> float:
        msg = str(error_message or "")
        m = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", msg, flags=re.IGNORECASE)
        if not m:
            return 0.0
        try:
            return max(0.0, float(m.group(1)))
        except Exception:
            return 0.0

    @staticmethod
    def _system_prompt(image_width: int, image_height: int) -> str:
        return (
            "You are a UI detector for automation. Output ONLY valid JSON. "
            "Do not output markdown. Do not output explanations. "
            "Do not use double quotes inside label or description text. "
            "Keep descriptions short, factual, and free of line breaks. "
            "The input image is already a crop of the visible screen. Detect every visible UI element inside that crop. "
            "including buttons, inputs, links, tabs, menus, checkboxes, radios, dropdowns, toggles, "
            "panes, taskbar items, toolbar controls, browser chrome, window chrome, sidebar entries, "
            "headings, labels, icons, status bars, and meaningful text. "
            "Prefer high recall over minimalism. If the screen is complex, return many small elements. "
            "Do not collapse the whole screen into only a few detections. "
            "Return this exact root shape with required fields: "
            "{image, image_size, coordinate_system, element_count, elements}. "
            "coordinate_system must be 'pixel'. "
            "All element coordinates must be relative to the crop/screen, not the full camera frame. "
            "You may return bounding boxes either as absolute pixel coordinates (integers) or as normalized fractions in [0,1]. "
            "If using normalized fractions, they are relative to the crop width/height. "
            "elements must be an array of objects with fields: "
            "id, type, label, description, state, dx, dy, confidence, source, bbox. "
            "confidence must be numeric in [0,1]. "
            "bbox must be a tight pixel box [x_min, y_min, x_max, y_max] around the element, "
            "using screen-local pixels, or a normalized [x_min, y_min, x_max, y_max] in [0,1]. "
            f"dx must be integer in [0,{image_width}]. "
            f"dy must be integer in [0,{image_height}]. "
            "source must be 'gemini_vlm'. "
            "element_count must equal elements array length. "
            "When uncertain, prefer a smaller accurate element over a wrong one, but do not omit visible UI "
            "that is clearly present. "
            "If no interactive elements are present, return element_count=0 and elements=[]."
        )

    @staticmethod
    def _broader_system_prompt(image_width: int, image_height: int) -> str:
        return (
            "You are a screen understanding model for desktop automation. Output ONLY valid JSON. "
            "Do not use double quotes inside label or description text. "
            "Keep descriptions short, factual, and free of line breaks. "
            "The input image is already a crop of the visible screen. Detect any visible UI structure inside that crop, including tabs, panes, menus, "
            "buttons, inputs, taskbar items, terminal controls, status bars, labels, icons, browser chrome, "
            "window chrome, sidebars, headings, and text. "
            "Prefer exhaustive reporting. Return many elements if the screen is dense. "
            "Return this exact root shape with required fields: "
            "{image, image_size, coordinate_system, element_count, elements}. "
            "coordinate_system must be 'pixel'. "
            "All element coordinates must be relative to the crop/screen, not the full camera frame. "
            "elements must be an array of objects with fields: "
            "id, type, label, description, state, dx, dy, confidence, source, bbox. "
            "confidence must be numeric in [0,1]. "
            "bbox must be a tight pixel box [x_min, y_min, x_max, y_max] around the element, "
            "using screen-local pixels. "
            f"dx must be integer in [0,{image_width}]. "
            f"dy must be integer in [0,{image_height}]. "
            "source must be 'gemini_vlm'. "
            "element_count must equal elements array length."
        )

    @staticmethod
    def _screen_detection_prompt(image_width: int, image_height: int) -> str:
        return (
            "You are locating the visible laptop or monitor screen in a camera photo. "
            "Output ONLY valid JSON. "
            "Detect the screen/display area inside the camera image, not the desk, keyboard, bezel, or other surroundings. "
            "Return the visible screen boundary as a tight pixel rectangle [x_min, y_min, x_max, y_max] in camera-image pixels. "
            "Also return the screen width and height as screen_size. "
            "If the display is partially visible, estimate the visible display area only. "
            "Return this exact root shape: {screen_bbox, screen_size}. "
            f"screen_bbox values must fit within x in [0,{image_width}] and y in [0,{image_height}]."
        )

    @staticmethod
    def _encode_image_array(
        image: Any,
        max_side: int = 1280,
    ) -> tuple[bytes, int, int, float, float]:
        if image is None:
            raise RuntimeError("Failed to prepare Gemini request image")

        original_h, original_w = image.shape[:2]
        req_w, req_h = original_w, original_h
        scale_x = 1.0
        scale_y = 1.0
        longest = max(original_w, original_h)
        if longest > max_side:
            scale = float(max_side) / float(longest)
            req_w = max(1, int(round(original_w * scale)))
            req_h = max(1, int(round(original_h * scale)))
            image = cv2.resize(image, (req_w, req_h), interpolation=cv2.INTER_AREA)
            scale_x = float(original_w) / float(req_w)
            scale_y = float(original_h) / float(req_h)

        ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            raise RuntimeError("Failed to encode Gemini request image")
        return buffer.tobytes(), req_w, req_h, scale_x, scale_y

    def _detect_screen_region(self, full_image: Any, request_options: Dict[str, Any]) -> tuple[int, int, int, int]:
        """Localize the visible screen in the camera frame."""
        h, w = full_image.shape[:2]

        try:
            bbox = detect_screen_bbox(full_image)
            x1, y1, x2, y2 = (int(v) for v in bbox)
            if x2 - x1 >= 32 and y2 - y1 >= 32:
                logger.info("Heuristic screen localization bbox=%s", [x1, y1, x2, y2])
                return (x1, y1, x2, y2)
        except Exception:
            logger.exception("Heuristic screen localization failed")

        image_bytes, request_width, request_height, _, _ = self._encode_image_array(full_image)
        prompt = self._screen_detection_prompt(request_width, request_height)
        generation_config = {
            "temperature": 0,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "object",
                "properties": {
                    "screen_bbox": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "screen_size": {
                        "type": "object",
                        "properties": {
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                        "required": ["width", "height"],
                    },
                },
                "required": ["screen_bbox", "screen_size"],
            },
        }

        try:
            response = self.client.generate_content(
                [
                    {"mime_type": "image/jpeg", "data": image_bytes},
                    prompt,
                ],
                generation_config=generation_config,
                request_options=request_options,
            )
            raw_text = str(getattr(response, "text", "") or "").strip()
            candidate = self._extract_best_json_object(raw_text) or raw_text
            data = json.loads(candidate)
            bbox = data.get("screen_bbox", [])
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)
                x1 = max(0, min(w - 1, x1))
                y1 = max(0, min(h - 1, y1))
                x2 = max(x1 + 1, min(w, x2))
                y2 = max(y1 + 1, min(h, y2))
                if x2 - x1 >= 32 and y2 - y1 >= 32:
                    logger.info("Gemini localized screen bbox=%s", [x1, y1, x2, y2])
                    return (x1, y1, x2, y2)
        except Exception:
            logger.exception("Gemini screen localization failed; falling back to full frame")

        return (0, 0, w, h)

    @staticmethod
    def _translate_bbox(
        bbox: Any,
        scale_x: float,
        scale_y: float,
        origin_x: int,
        origin_y: int,
        image_width: int,
        image_height: int,
    ) -> List[int] | None:
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return None
        try:
            # Support two common bbox formats returned by VLMs:
            # 1) Absolute pixel coordinates in the request image (e.g., [x1_px, y1_px, x2_px, y2_px])
            # 2) Normalized fractions in [0,1] relative to the crop (e.g., [x1_frac, y1_frac, x2_frac, y2_frac])
            vals = [float(v) for v in bbox]
            # If values are normalized fractions (all <= 1.0), map to crop pixels using image_width/height
            if all(0.0 <= v <= 1.0 for v in vals):
                x1 = int(round(vals[0] * float(image_width))) + int(origin_x)
                y1 = int(round(vals[1] * float(image_height))) + int(origin_y)
                x2 = int(round(vals[2] * float(image_width))) + int(origin_x)
                y2 = int(round(vals[3] * float(image_height))) + int(origin_y)
            else:
                # Values are in request-image pixels; scale them back to crop pixels using scale_x/scale_y
                x1 = int(round(vals[0] * float(scale_x))) + int(origin_x)
                y1 = int(round(vals[1] * float(scale_y))) + int(origin_y)
                x2 = int(round(vals[2] * float(scale_x))) + int(origin_x)
                y2 = int(round(vals[3] * float(scale_y))) + int(origin_y)
        except Exception:
            return None
        x1 = max(0, min(image_width - 1, x1))
        y1 = max(0, min(image_height - 1, y1))
        x2 = max(x1 + 1, min(image_width, x2))
        y2 = max(y1 + 1, min(image_height, y2))
        return [x1, y1, x2, y2]

    @staticmethod
    def _extract_best_json_object(text: str) -> str:
        """Extract the largest balanced {...} JSON object from mixed text."""
        start = text.find("{")
        if start < 0:
            return ""
        depth = 0
        in_str = False
        esc = False
        best = ""
        current_start = -1
        for i, ch in enumerate(text):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == "\"":
                    in_str = False
                continue
            if ch == "\"":
                in_str = True
                continue
            if ch == "{":
                if depth == 0:
                    current_start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and current_start >= 0:
                        cand = text[current_start : i + 1].strip()
                        if len(cand) > len(best):
                            best = cand
                        current_start = -1
        return best

    @staticmethod
    def _sanitize_json_string(s: str) -> str:
        if not s:
            return s
        s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
        s = re.sub(r",\s*}\s*", "}\n", s)
        s = re.sub(r",\s*\]\s*", "]\n", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s

    @staticmethod
    def _close_unbalanced_json(s: str) -> str:
        """Best-effort closure for truncated JSON text."""
        depth = 0
        in_str = False
        esc = False
        stack: List[str] = []
        for ch in s:
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == "\"":
                    in_str = False
                continue
            if ch == "\"":
                in_str = True
                continue
            if ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]":
                if stack and stack[-1] == ch:
                    stack.pop()
        return s + "".join(reversed(stack))

    @staticmethod
    def _coerce_json_text(text: str) -> str:
        """Best-effort conversion of a JS-like object string into valid JSON."""
        s = text.replace("```json", "").replace("```", "")
        s = re.sub(r"//.*?$|/\*.*?\*/", "", s, flags=re.DOTALL | re.MULTILINE)
        s = s.replace("\u2018", "'").replace("\u2019", "'")
        s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', s)
        s = re.sub(r'([\{,\s])([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
        s = re.sub(r",\s*([}\]])", r"\1", s)
        s = re.sub(r"\bTrue\b", "true", s)
        s = re.sub(r"\bFalse\b", "false", s)
        s = re.sub(r"\bNone\b", "null", s)
        return s

    @staticmethod
    def _region_specs(image_width: int, image_height: int) -> List[tuple[str, int, int, int, int]]:
        overlap_x = max(80, int(round(image_width * 0.18)))
        overlap_y = max(80, int(round(image_height * 0.18)))
        mid_x = image_width // 2
        mid_y = image_height // 2

        def _clamp_bounds(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int, int]:
            x1 = max(0, min(image_width - 1, x1))
            y1 = max(0, min(image_height - 1, y1))
            x2 = max(x1 + 1, min(image_width, x2))
            y2 = max(y1 + 1, min(image_height, y2))
            return x1, y1, x2, y2

        return [
            ("top_left", *_clamp_bounds(0, 0, mid_x + overlap_x, mid_y + overlap_y)),
            ("top_right", *_clamp_bounds(mid_x - overlap_x, 0, image_width, mid_y + overlap_y)),
            ("bottom_left", *_clamp_bounds(0, mid_y - overlap_y, mid_x + overlap_x, image_height)),
            ("bottom_right", *_clamp_bounds(mid_x - overlap_x, mid_y - overlap_y, image_width, image_height)),
        ]

    @staticmethod
    def _extract_partial_elements(response_text: str) -> List[Dict[str, Any]]:
        """
        Recover complete element objects from a truncated Gemini response.

        The model occasionally stops mid-array. We keep any fully closed element
        objects that appear before the truncation point so the pipeline can
        continue with partial but useful output.
        """
        key_match = re.search(r'"elements"\s*:\s*\[', response_text)
        if not key_match:
            return []

        idx = key_match.end()
        elements: List[Dict[str, Any]] = []
        in_str = False
        esc = False
        brace_depth = 0
        obj_start: int | None = None

        while idx < len(response_text):
            ch = response_text[idx]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    if brace_depth == 0:
                        obj_start = idx
                    brace_depth += 1
                elif ch == "}":
                    if brace_depth > 0:
                        brace_depth -= 1
                        if brace_depth == 0 and obj_start is not None:
                            candidate = response_text[obj_start : idx + 1].strip()
                            parsed: Any = None
                            for variant in (
                                candidate,
                                GeminiVLM._sanitize_json_string(candidate),
                                GeminiVLM._coerce_json_text(candidate),
                                GeminiVLM._close_unbalanced_json(candidate),
                                GeminiVLM._close_unbalanced_json(GeminiVLM._sanitize_json_string(candidate)),
                                GeminiVLM._close_unbalanced_json(GeminiVLM._coerce_json_text(candidate)),
                            ):
                                try:
                                    parsed = json.loads(variant)
                                    break
                                except json.JSONDecodeError:
                                    continue
                            if isinstance(parsed, dict):
                                elements.append(parsed)
                            obj_start = None
                elif ch == "]" and brace_depth == 0:
                    break
            idx += 1

        return elements

    def _recover_partial_payload(
        self,
        raw_text: str,
        image_path: str,
        image_width: int,
        image_height: int,
    ) -> Dict[str, Any] | None:
        partial_elements = self._extract_partial_elements(raw_text)
        if not partial_elements:
            return None

        logger.warning(
            "Recovered %d complete elements from truncated Gemini response",
            len(partial_elements),
        )
        return {
            "image": image_path,
            "image_size": {"width": int(image_width), "height": int(image_height)},
            "coordinate_system": "pixel",
            "element_count": len(partial_elements),
            "elements": partial_elements,
            "_vlm_error_type": "partial_recovery",
        }

    def _parse_json_payload(
        self,
        raw_text: str,
        image_path: str,
        image_width: int,
        image_height: int,
    ) -> Dict[str, Any]:
        if not raw_text:
            logger.warning("Gemini returned empty response content")
            return self._safe_empty_response(
                image_path, image_width, image_height, vlm_error_type="parse_error"
            )

        candidate = raw_text.strip()
        logger.debug("Raw Gemini response (trimmed): %s", candidate[:2000])
        if candidate.startswith("```"):
            candidate = candidate.replace("```json", "").replace("```", "").strip()

        parsed: Any
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            extracted = self._extract_best_json_object(candidate)
            extracted_array = candidate if candidate.lstrip().startswith("[") else ""
            if not extracted and not extracted_array:
                recovered = self._recover_partial_payload(candidate, image_path, image_width, image_height)
                if recovered is not None:
                    return recovered
                try:
                    debug_path = f"{image_path}.gemini_raw.txt"
                    with open(debug_path, "w", encoding="utf-8") as fh:
                        fh.write(candidate[:20000])
                    logger.warning("Wrote raw Gemini response to %s", debug_path)
                except Exception:
                    logger.exception("Failed writing raw Gemini response to disk")
                logger.exception("No JSON object found in Gemini response")
                return self._safe_empty_response(
                    image_path, image_width, image_height, vlm_error_type="parse_error"
                )

            parse_candidates = [c for c in (extracted, extracted_array) if c]
            parsed = None
            for text in parse_candidates:
                for variant in (
                    text,
                    self._sanitize_json_string(text),
                    self._coerce_json_text(text),
                    self._close_unbalanced_json(self._sanitize_json_string(text)),
                    self._close_unbalanced_json(self._coerce_json_text(text)),
                ):
                    try:
                        parsed = json.loads(variant)
                        break
                    except json.JSONDecodeError:
                        continue
                if parsed is not None:
                    break

            if parsed is None:
                recovered = self._recover_partial_payload(candidate, image_path, image_width, image_height)
                if recovered is not None:
                    return recovered
                try:
                    debug_path = f"{image_path}.gemini_raw.txt"
                    with open(debug_path, "w", encoding="utf-8") as fh:
                        fh.write(candidate[:20000])
                    logger.warning("Wrote raw Gemini response to %s", debug_path)
                except Exception:
                    logger.exception("Failed writing raw Gemini response to disk")
                logger.exception("Failed parsing Gemini JSON response after repair attempts")
                return self._safe_empty_response(
                    image_path, image_width, image_height, vlm_error_type="parse_error"
                )

        if isinstance(parsed, list) and parsed:
            parsed = parsed[0] if isinstance(parsed[0], dict) else None

        if not isinstance(parsed, dict):
            logger.warning("Parsed Gemini response is not a JSON object")
            return self._safe_empty_response(
                image_path, image_width, image_height, vlm_error_type="parse_error"
            )

        return parsed

    def _request_strict_json_retry(
        self,
        image_bytes: bytes,
        image_path: str,
        image_width: int,
        image_height: int,
        request_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        retry_prompt = (
            self._system_prompt(image_width, image_height)
            + " IMPORTANT: Return at most 25 elements. "
            "Keep each description under 12 words. "
            "Return STRICT JSON only with double quotes and no trailing commas."
        )
        try:
            response = self.client.generate_content(
                [
                    {"mime_type": "image/png", "data": image_bytes},
                    retry_prompt,
                ],
                generation_config={
                    "temperature": 0,
                    "max_output_tokens": 8192,
                    "response_mime_type": "application/json",
                },
                request_options=request_options,
            )
        except Exception:
            logger.exception("Gemini strict-json retry request failed")
            return self._safe_empty_response(
                image_path, image_width, image_height, vlm_error_type="api_error"
            )

        raw = str(getattr(response, "text", "") or "")
        return self._parse_json_payload(raw, image_path, image_width, image_height)

    def _request_broader_retry(
        self,
        image_bytes: bytes,
        image_path: str,
        image_width: int,
        image_height: int,
        request_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        retry_prompt = (
            self._broader_system_prompt(image_width, image_height)
            + " IMPORTANT: Return every visible screen region that appears to be a UI element. "
            "Do not suppress tabs, panes, taskbar items, or terminal controls. "
            "If there are visible controls, return them."
        )
        try:
            response = self.client.generate_content(
                [
                    {"mime_type": "image/png", "data": image_bytes},
                    retry_prompt,
                ],
                generation_config={
                    "temperature": 0,
                    "max_output_tokens": 8192,
                    "response_mime_type": "application/json",
                },
                request_options=request_options,
            )
        except Exception:
            logger.exception("Gemini broader retry request failed")
            return self._safe_empty_response(
                image_path, image_width, image_height, vlm_error_type="api_error"
            )

        raw = str(getattr(response, "text", "") or "")
        return self._parse_json_payload(raw, image_path, image_width, image_height)

    @staticmethod
    def _normalize_payload(
        payload: Dict[str, Any],
        image_path: str,
        image_width: int,
        image_height: int,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        origin_x: int = 0,
        origin_y: int = 0,
        screen_width: int | None = None,
        screen_height: int | None = None,
    ) -> Dict[str, Any]:
        normalized = GeminiVLM._safe_empty_response(image_path, image_width, image_height)
        normalized["image"] = image_path
        normalized["image_size"] = {"width": int(image_width), "height": int(image_height)}
        screen_w = max(1, int(screen_width if screen_width is not None else image_width))
        screen_h = max(1, int(screen_height if screen_height is not None else image_height))
        normalized["screen_bbox"] = [
            max(0, int(origin_x)),
            max(0, int(origin_y)),
            max(0, int(origin_x + screen_w)),
            max(0, int(origin_y + screen_h)),
        ]
        normalized["screen_size"] = {"width": screen_w, "height": screen_h}

        raw_elements = payload.get("elements", [])
        if not isinstance(raw_elements, list):
            raw_elements = []

        elements: List[Dict[str, Any]] = []
        for idx, element in enumerate(raw_elements):
            if not isinstance(element, dict):
                continue

            translated_bbox = GeminiVLM._translate_bbox(
                element.get("bbox"),
                scale_x=scale_x,
                scale_y=scale_y,
                origin_x=0,
                origin_y=0,
                image_width=screen_w,
                image_height=screen_h,
            )

            try:
                dx = int(round(float(element.get("dx", 0)) * float(scale_x)))
                dy = int(round(float(element.get("dy", 0)) * float(scale_y)))
            except Exception:
                dx, dy = 0, 0
            if translated_bbox is not None:
                dx = int(round((translated_bbox[0] + translated_bbox[2]) * 0.5))
                dy = int(round((translated_bbox[1] + translated_bbox[3]) * 0.5))

            try:
                confidence = float(element.get("confidence", 0.0))
            except Exception:
                confidence = 0.0

            elements.append(
                {
                    "id": str(element.get("id", f"elem_{idx}")),
                    "type": str(element.get("type", "unknown")),
                    "label": str(element.get("label", "")),
                    "description": str(element.get("description", "")),
                    "state": str(element.get("state", "normal")),
                    "dx": max(0, min(screen_w, dx)),
                    "dy": max(0, min(screen_h, dy)),
                    "bbox": translated_bbox,
                    "frame_bbox": (
                        [
                            max(0, min(image_width - 1, int(round(origin_x + translated_bbox[0])))),
                            max(0, min(image_height - 1, int(round(origin_y + translated_bbox[1])))),
                            max(0, min(image_width, int(round(origin_x + translated_bbox[2])))),
                            max(0, min(image_height, int(round(origin_y + translated_bbox[3])))),
                        ]
                        if translated_bbox is not None
                        else None
                    ),
                    "frame_dx": (
                        max(0, min(image_width - 1, int(round(origin_x + dx))))
                    ),
                    "frame_dy": (
                        max(0, min(image_height - 1, int(round(origin_y + dy))))
                    ),
                    "confidence": max(0.0, min(1.0, confidence)),
                    "source": str(element.get("source", "gemini_vlm")),
                }
            )

        normalized["elements"] = elements
        normalized["element_count"] = len(elements)
        for key in ("_vlm_error_type", "_vlm_error", "_vlm_retry_after_seconds"):
            if key in payload:
                normalized[key] = payload[key]
        return normalized

    @staticmethod
    def _refine_elements_with_image(
        elements: List[Dict[str, Any]],
        image: Any,
        origin_x: int = 0,
        origin_y: int = 0,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Refine pixel bboxes against image evidence and keep frame coordinates in sync."""
        if image is None or getattr(image, "size", 0) == 0:
            return elements

        try:
            from src.perception.grounding.bbox_refiner import BBoxRefiner
        except Exception:
            logger.exception("BBox refiner import failed; keeping original detections")
            return elements

        try:
            refiner = BBoxRefiner()
            h, w = image.shape[:2]
        except Exception:
            logger.exception("BBox refiner initialization failed; keeping original detections")
            return elements

        frame_w = int(frame_width if frame_width is not None else w)
        frame_h = int(frame_height if frame_height is not None else h)
        refined_elements: List[Dict[str, Any]] = []

        for elem in elements:
            updated = dict(elem)
            bbox = updated.get("bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                try:
                    x1, y1, x2, y2 = (float(v) for v in bbox)
                    bbox_norm = (
                        max(0.0, min(1.0, x1 / float(w))),
                        max(0.0, min(1.0, y1 / float(h))),
                        max(0.0, min(1.0, x2 / float(w))),
                        max(0.0, min(1.0, y2 / float(h))),
                    )
                    refined_norm = refiner.refine_bbox(image, bbox_norm)
                    rx1 = int(round(refined_norm[0] * float(w)))
                    ry1 = int(round(refined_norm[1] * float(h)))
                    rx2 = int(round(refined_norm[2] * float(w)))
                    ry2 = int(round(refined_norm[3] * float(h)))
                    cx = int(round((rx1 + rx2) / 2.0))
                    cy = int(round((ry1 + ry2) / 2.0))

                    updated["bbox"] = [rx1, ry1, rx2, ry2]
                    updated["dx"] = max(0, min(w, cx))
                    updated["dy"] = max(0, min(h, cy))
                    updated["frame_bbox"] = [
                        max(0, min(frame_w - 1, int(round(origin_x + rx1)))),
                        max(0, min(frame_h - 1, int(round(origin_y + ry1)))),
                        max(0, min(frame_w, int(round(origin_x + rx2)))),
                        max(0, min(frame_h, int(round(origin_y + ry2)))),
                    ]
                    updated["frame_dx"] = max(0, min(frame_w - 1, int(round(origin_x + cx))))
                    updated["frame_dy"] = max(0, min(frame_h - 1, int(round(origin_y + cy))))
                except Exception:
                    logger.exception("BBox refinement failed for element id=%s", updated.get("id", "unknown"))

            refined_elements.append(updated)

        return refined_elements

    @staticmethod
    def _response_schema(image_width: int, image_height: int) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image": {"type": "string"},
                "image_size": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                    "required": ["width", "height"],
                },
                "coordinate_system": {"type": "string"},
                "element_count": {"type": "integer"},
                "elements": {
                    "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                            "label": {"type": "string"},
                            "description": {"type": "string"},
                        "state": {"type": "string"},
                        "dx": {"type": "integer"},
                        "dy": {"type": "integer"},
                        "bbox": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "confidence": {"type": "number"},
                        "source": {"type": "string"},
                    },
                    "required": [
                        "id",
                            "type",
                            "label",
                            "description",
                        "state",
                        "dx",
                        "dy",
                        "confidence",
                        "source",
                    ],
                },
            },
            },
            "required": ["image", "image_size", "coordinate_system", "element_count", "elements"],
        }

    @staticmethod
    def _prepare_request_image(
        image_path: str,
        max_side: int = 1280,
    ) -> tuple[bytes, int, int, float, float]:
        image = cv2.imread(image_path)
        if image is None:
            raise RuntimeError(f"Failed to read image: {image_path}")
        original_h, original_w = image.shape[:2]
        req_w, req_h = original_w, original_h
        scale_x = 1.0
        scale_y = 1.0

        longest = max(original_w, original_h)
        if longest > max_side:
            scale = float(max_side) / float(longest)
            req_w = max(1, int(round(original_w * scale)))
            req_h = max(1, int(round(original_h * scale)))
            image = cv2.resize(image, (req_w, req_h), interpolation=cv2.INTER_AREA)
            scale_x = float(original_w) / float(req_w)
            scale_y = float(original_h) / float(req_h)

        ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            raise RuntimeError("Failed to encode Gemini request image")
        return buffer.tobytes(), req_w, req_h, scale_x, scale_y

    @staticmethod
    def _dedupe_elements(elements: List[Dict[str, Any]], distance_threshold: int = 42) -> List[Dict[str, Any]]:
        def _norm_label(label: Any) -> str:
            return " ".join(str(label or "").strip().lower().split())

        kept: List[Dict[str, Any]] = []
        for element in sorted(elements, key=lambda e: float(e.get("confidence", 0.0)), reverse=True):
            try:
                dx = int(round(float(element.get("dx", 0))))
                dy = int(round(float(element.get("dy", 0))))
            except Exception:
                dx, dy = 0, 0
            elem_type = str(element.get("type", "unknown")).strip().lower()
            label = _norm_label(element.get("label", ""))
            duplicate = False
            for existing in kept:
                existing_type = str(existing.get("type", "unknown")).strip().lower()
                existing_label = _norm_label(existing.get("label", ""))
                if elem_type != existing_type:
                    continue
                if not label or not existing_label or label != existing_label:
                    continue
                try:
                    ex_dx = int(round(float(existing.get("dx", 0))))
                    ex_dy = int(round(float(existing.get("dy", 0))))
                except Exception:
                    ex_dx, ex_dy = 0, 0
                if abs(dx - ex_dx) <= distance_threshold and abs(dy - ex_dy) <= distance_threshold:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(element)
        return kept

    def _analyze_region(
        self,
        full_image: Any,
        image_path: str,
        image_width: int,
        image_height: int,
        region_name: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        request_options: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        crop = full_image[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return []

        try:
            image_bytes, request_width, request_height, scale_x, scale_y = self._encode_image_array(crop)
        except Exception:
            logger.exception("Failed to prepare Gemini crop for region=%s", region_name)
            return []

        region_prompt = (
            self._system_prompt(request_width, request_height)
            + "\n\n"
            f"You are analyzing the {region_name} crop of a larger screen.\n"
            f"The crop corresponds to full-image coordinates x={x1}..{x2} and y={y1}..{y2}.\n"
            "Report dx and dy in crop-local pixels.\n"
            "You may return bbox either as pixel coordinates or normalized fractions in [0,1].\n"
            "Return every visible UI element in this crop, including text, labels, icons, controls, tabs, "
            "browser chrome, window chrome, sidebars, toolbars, headings, and panels.\n"
            "Prefer exhaustive recall over minimalism."
        )
        generation_config = {
            "temperature": 0,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
            "response_schema": self._response_schema(request_width, request_height),
        }

        try:
            response = self.client.generate_content(
                [
                    {"mime_type": "image/jpeg", "data": image_bytes},
                    region_prompt,
                ],
                generation_config=generation_config,
                request_options=request_options,
            )
        except Exception:
            logger.exception("Gemini region scan failed for %s", region_name)
            return []

        raw_text = str(getattr(response, "text", "") or "")
        parsed = self._parse_json_payload(raw_text, image_path, request_width, request_height)
        if int(parsed.get("element_count", 0) or 0) <= 0:
            return []

        normalized = self._normalize_payload(
            parsed,
            image_path,
            image_width,
            image_height,
            scale_x=scale_x,
            scale_y=scale_y,
            origin_x=x1,
            origin_y=y1,
        )
        normalized["elements"] = self._refine_elements_with_image(
            list(normalized.get("elements", [])),
            crop,
            origin_x=x1,
            origin_y=y1,
            frame_width=image_width,
            frame_height=image_height,
        )

        return list(normalized.get("elements", []))

    def analyze(self, image_path: str, image_width: int, image_height: int) -> Dict[str, Any]:
        """Analyze a screenshot using Gemini and return structured UI coordinates."""
        logger.info(
            "Gemini analyze started image=%s size=%dx%d model=%s",
            image_path,
            image_width,
            image_height,
            self.model_name,
        )

        full_image = cv2.imread(image_path)
        if full_image is None:
            logger.error("Failed to load image: %s", image_path)
            return self._safe_empty_response(image_path, image_width, image_height, vlm_error_type="api_error")

        request_options = {"timeout": int(max(1.0, self.timeout_seconds))}
        if self._is_screenshot_mode():
            screen_x1, screen_y1, screen_x2, screen_y2 = 0, 0, full_image.shape[1], full_image.shape[0]
        else:
            screen_x1, screen_y1, screen_x2, screen_y2 = self._detect_screen_region(full_image, request_options)
        screen_crop = full_image[screen_y1:screen_y2, screen_x1:screen_x2]
        if screen_crop is None or screen_crop.size == 0:
            logger.warning("Screen crop was empty; falling back to full frame")
            screen_x1, screen_y1, screen_x2, screen_y2 = 0, 0, full_image.shape[1], full_image.shape[0]
            screen_crop = full_image

        image_bytes, request_width, request_height, scale_x, scale_y = self._encode_image_array(screen_crop)

        full_prompt = (
            self._system_prompt(request_width, request_height)
            + "\n\nAnalyze this screenshot and return only the JSON object."
        )
        if self._is_screenshot_mode():
            full_prompt += (
                " This is a direct desktop screenshot. Do not detect a separate screen boundary."
                " Treat the full image as the screen and keep screen_bbox equal to the image bounds."
            )

        payload = [
            {"mime_type": "image/jpeg", "data": image_bytes},
            full_prompt,
        ]
        generation_config = {
            "temperature": 0,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
            "response_schema": self._response_schema(request_width, request_height),
        }

        try:
            logger.debug(
                "Gemini request prepared prompt_chars=%d timeout=%s",
                len(full_prompt),
                request_options["timeout"],
            )
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
                    try:
                        response = self.client.generate_content(
                            payload,
                            generation_config=generation_config,
                            request_options=request_options,
                        )
                    except Exception:
                        logger.exception("Gemini API request failed after fallback retry")
                        return self._safe_empty_response(
                            image_path,
                            image_width,
                            image_height,
                            vlm_error_type="api_error",
                        )
                else:
                    logger.exception("Gemini API request failed")
                    return self._safe_empty_response(
                        image_path,
                        image_width,
                        image_height,
                        vlm_error_type="model_unavailable",
                    )
            else:
                logger.exception("Gemini API request failed")
                error_type = (
                    "quota_exceeded"
                    if "resource_exhausted" in msg or "quota exceeded" in msg
                    else "api_error"
                )
                retry_after = self._extract_retry_after_seconds(str(exc))
                return self._safe_empty_response(
                    image_path,
                    image_width,
                    image_height,
                    vlm_error_type=error_type,
                    vlm_error=str(exc),
                    vlm_retry_after_seconds=retry_after,
                )

        raw_text = str(getattr(response, "text", "") or "")
        logger.info("Gemini returned %d characters", len(raw_text))
        parsed = self._parse_json_payload(raw_text, image_path, request_width, request_height)
        parsed_error = str(parsed.get("_vlm_error_type", "")).strip().lower()

        if parsed_error == "parse_error" and int(parsed.get("element_count", 0) or 0) <= 0:
            logger.warning("First Gemini parse failed; retrying with a stricter JSON prompt")
            retry_payload = self._request_strict_json_retry(
                image_bytes,
                image_path,
                request_width,
                request_height,
                request_options,
            )
            retry_error = str(retry_payload.get("_vlm_error_type", "")).strip().lower()
            if int(retry_payload.get("element_count", 0) or 0) > 0 and retry_error != "parse_error":
                parsed = retry_payload
                parsed_error = retry_error
            else:
                logger.warning("Strict JSON retry did not recover elements; trying broader prompt")
                broader_payload = self._request_broader_retry(
                    image_bytes,
                    image_path,
                    request_width,
                    request_height,
                    request_options,
                )
                broader_error = str(broader_payload.get("_vlm_error_type", "")).strip().lower()
                if int(broader_payload.get("element_count", 0) or 0) > 0 and broader_error != "parse_error":
                    parsed = broader_payload
                    parsed_error = broader_error

        normalized = self._normalize_payload(
            parsed,
            image_path,
            image_width,
            image_height,
            scale_x=scale_x,
            scale_y=scale_y,
            origin_x=screen_x1,
            origin_y=screen_y1,
            screen_width=screen_crop.shape[1],
            screen_height=screen_crop.shape[0],
        )

        if self._is_screenshot_mode() and normalized.get("element_count", 0) < 12:
            region_elements: List[Dict[str, Any]] = []
            for region_name, x1, y1, x2, y2 in self._region_specs(image_width, image_height):
                region_elements.extend(
                    self._analyze_region(
                        full_image,
                        image_path,
                        image_width,
                        image_height,
                        region_name,
                        x1,
                        y1,
                        x2,
                        y2,
                        request_options,
                    )
                )

            if region_elements:
                merged = list(normalized.get("elements", [])) + region_elements
                normalized["elements"] = self._dedupe_elements(merged)
                normalized["element_count"] = len(normalized["elements"])

        logger.info(
            "Gemini analyze completed image=%s elements=%d error_type=%s",
            image_path,
            normalized.get("element_count", 0),
            normalized.get("_vlm_error_type", ""),
        )
        return normalized
