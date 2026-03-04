"""Gemini powered semantic VLM implementation for screen-aware agents."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from src.vision.config import GEMINI_API_KEY, MODEL_NAME
from src.vision.vlm.base_vlm import BaseVLM

logger = logging.getLogger(__name__)


class GeminiVLM(BaseVLM):
    """
    Semantic VLM adapter using Gemini.

    The output is normalized to dx/dy pixel points for automation.
    """

    def __init__(self, model_name: str = MODEL_NAME, timeout_seconds: float = 45.0) -> None:
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        if not GEMINI_API_KEY:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. Set it in .env or export it before using provider=gemini."
            )
        try:
            import google.generativeai as genai

            self._genai = genai
            self._genai.configure(api_key=GEMINI_API_KEY)
            self.model_name = self._resolve_model_name(self.model_name)
            self.client = self._genai.GenerativeModel(self.model_name)
        except ImportError as exc:
            raise ImportError(
                "google-generativeai package not installed. Run: pip install google-generativeai"
            ) from exc

    def _resolve_model_name(self, requested_model: str) -> str:
        """Pick a generateContent-capable Gemini model, preferring requested model."""
        try:
            models = list(self._genai.list_models())
            supported = []
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

    @staticmethod
    def _safe_empty_response(
        image_path: str,
        image_width: int,
        image_height: int,
        vlm_error_type: str = "",
        vlm_error: str = "",
        vlm_retry_after_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        payload = {
            "image": image_path,
            "image_size": {"width": int(image_width), "height": int(image_height)},
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
            "Detect ONLY interactive UI elements (buttons, inputs, links, tabs, menus, checkboxes, radios, dropdowns, toggles). "
            "Do not include decorative text-only or background elements. "
            "Return this exact root shape with required fields: "
            "{image, image_size, coordinate_system, element_count, elements}. "
            "coordinate_system must be 'pixel'. "
            "elements must be an array of objects with fields: "
            "id, type, label, description, state, dx, dy, confidence, source. "
            "confidence must be numeric in [0,1]. "
            f"dx must be integer in [0,{image_width}]. "
            f"dy must be integer in [0,{image_height}]. "
            "source must be 'gemini_vlm'. "
            "element_count must equal elements array length. "
            "When uncertain, return fewer elements instead of guessing. "
            "If no interactive elements are present, return element_count=0 and elements=[]."
        )

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
        if candidate.startswith("```"):
            candidate = candidate.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            extracted = self._extract_best_json_object(candidate)
            if extracted:
                try:
                    parsed = json.loads(extracted)
                except json.JSONDecodeError:
                    logger.exception("Failed parsing Gemini JSON response")
                    return self._safe_empty_response(
                        image_path, image_width, image_height, vlm_error_type="parse_error"
                    )
            else:
                logger.exception("No JSON object found in Gemini response")
                return self._safe_empty_response(
                    image_path, image_width, image_height, vlm_error_type="parse_error"
                )

        if not isinstance(parsed, dict):
            logger.warning("Parsed Gemini response is not a JSON object")
            return self._safe_empty_response(
                image_path, image_width, image_height, vlm_error_type="parse_error"
            )

        return parsed

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

    def analyze(self, image_path: str, image_width: int, image_height: int) -> Dict[str, Any]:
        """Analyze a screenshot using Gemini and return structured UI coordinates."""
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        full_prompt = (
            self._system_prompt(image_width, image_height)
            + "\n\nAnalyze this screenshot and return only the JSON object."
        )

        payload = [
            {"mime_type": "image/png", "data": image_bytes},
            full_prompt,
        ]
        generation_config = {
            "temperature": 0,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }
        request_options = {"timeout": int(max(1.0, self.timeout_seconds))}

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
                error_type = "quota_exceeded" if "resource_exhausted" in msg or "quota exceeded" in msg else "api_error"
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
        parsed = self._parse_json_payload(raw_text, image_path, image_width, image_height)
        if str(parsed.get("_vlm_error_type", "")).strip().lower() == "parse_error":
            logger.warning("Gemini returned malformed JSON; retrying with strict compact JSON prompt")
            parsed = self._request_strict_json_retry(
                image_bytes=image_bytes,
                image_path=image_path,
                image_width=image_width,
                image_height=image_height,
                request_options=request_options,
            )

        parsed.setdefault("image", image_path)
        parsed.setdefault("image_size", {"width": int(image_width), "height": int(image_height)})
        parsed.setdefault("coordinate_system", "pixel")
        parsed.setdefault("elements", [])
        parsed.setdefault("element_count", len(parsed.get("elements", [])))

        return parsed
