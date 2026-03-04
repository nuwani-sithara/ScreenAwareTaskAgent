"""OpenAI GPT-4o powered semantic VLM implementation for screen-aware agents."""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

from src.vision.config import MODEL_NAME
from src.vision.vlm.base_vlm import BaseVLM

logger = logging.getLogger(__name__)


class OpenAIVLM(BaseVLM):
    """
    Semantic VLM adapter using GPT-4o.

    Research note:
    - GPT-4o is used as a semantic VLM for UI understanding.
    - dx/dy pixel points are used for click automation.
    - Bounding boxes are intentionally removed from this output format.
    """

    def __init__(self, model_name: str = MODEL_NAME, timeout_seconds: float = 45.0) -> None:
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set.")
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=openai_api_key)
        except ImportError as exc:
            raise ImportError("openai package not installed. Run: pip install openai") from exc

    @staticmethod
    def _encode_image_base64(image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def _safe_empty_response(image_path: str, image_width: int, image_height: int) -> Dict[str, Any]:
        return {
            "image": image_path,
            "image_size": {"width": int(image_width), "height": int(image_height)},
            "coordinate_system": "pixel",
            "element_count": 0,
            "elements": [],
        }

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
            "source must be 'gpt4o_vlm'. "
            "element_count must equal elements array length. "
            "When uncertain, return fewer elements instead of guessing. "
            "If no interactive elements are present, return element_count=0 and elements=[]."
        )

    def _extract_text_content(self, response: Any) -> str:
        content = ""
        try:
            content = response.choices[0].message.content
        except Exception:
            pass

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
            return "\n".join(text_parts).strip()

        return ""

    def _parse_json_payload(
        self,
        raw_text: str,
        image_path: str,
        image_width: int,
        image_height: int,
    ) -> Dict[str, Any]:
        if not raw_text:
            logger.warning("OpenAI returned empty response content")
            return self._safe_empty_response(image_path, image_width, image_height)

        candidate = raw_text.strip()
        if candidate.startswith("```"):
            candidate = candidate.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(candidate[start : end + 1])
                except json.JSONDecodeError:
                    logger.exception("Failed parsing model JSON response")
                    return self._safe_empty_response(image_path, image_width, image_height)
            else:
                logger.exception("No JSON object found in model response")
                return self._safe_empty_response(image_path, image_width, image_height)

        if not isinstance(parsed, dict):
            logger.warning("Parsed model response is not a JSON object")
            return self._safe_empty_response(image_path, image_width, image_height)

        return parsed

    def analyze(self, image_path: str, image_width: int, image_height: int) -> Dict[str, Any]:
        """Analyze a screenshot using GPT-4o and return structured UI coordinates."""
        image_b64 = self._encode_image_base64(image_path)
        system_prompt = self._system_prompt(image_width, image_height)

        user_prompt = (
            f"Analyze this screenshot: {image_path}. "
            "Return only the JSON object and follow all constraints exactly."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                temperature=0,
                timeout=self.timeout_seconds,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            },
                        ],
                    },
                ],
            )
        except Exception:
            logger.exception("OpenAI API request failed")
            return self._safe_empty_response(image_path, image_width, image_height)

        raw_text = self._extract_text_content(response)
        parsed = self._parse_json_payload(raw_text, image_path, image_width, image_height)

        parsed.setdefault("image", image_path)
        parsed.setdefault("image_size", {"width": int(image_width), "height": int(image_height)})
        parsed.setdefault("coordinate_system", "pixel")
        parsed.setdefault("elements", [])
        parsed.setdefault("element_count", len(parsed.get("elements", [])))

        return parsed
