"""OpenAI-backed semantic VLM implementation for screen-aware agents."""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from src.vision.config import MODEL_NAME, OPENAI_API_KEY
from src.vision.vlm.gemini_vlm import GeminiVLM as _GeminiVLM

logger = logging.getLogger(__name__)


@dataclass
class _OpenAIResponse:
    text: str


class _OpenAIShimClient:
    """Minimal Gemini-compatible client wrapper around the OpenAI Responses API."""

    def __init__(self, api_key: str, model_name: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = float(timeout_seconds)

    @staticmethod
    def _ensure_openai_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
        def _walk(node: Any) -> Any:
            if isinstance(node, dict):
                new_node = dict(node)
                node_type = new_node.get("type")
                if node_type == "object":
                    props = new_node.get("properties", {})
                    if isinstance(props, dict):
                            new_node["properties"] = {key: _walk(value) for key, value in props.items()}
                            # Ensure the 'required' array exists and includes every property key.
                            prop_keys = list(new_node["properties"].keys())
                            existing_required = new_node.get("required")
                            if not isinstance(existing_required, list) or set(existing_required) != set(prop_keys):
                                new_node["required"] = prop_keys
                    new_node.setdefault("additionalProperties", False)
                elif node_type == "array" and isinstance(new_node.get("items"), (dict, list)):
                    new_node["items"] = _walk(new_node["items"])
                return new_node
            if isinstance(node, list):
                return [_walk(item) for item in node]
            return node

        return _walk(schema)

    @staticmethod
    def _image_to_data_url(image_bytes: bytes) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    @staticmethod
    def _extract_prompt_parts(payload: List[Any]) -> tuple[str, str, bytes]:
        user_prompt_parts: List[str] = []
        image_bytes: bytes = b""

        for item in payload:
            if isinstance(item, dict) and "data" in item:
                maybe_bytes = item.get("data")
                if isinstance(maybe_bytes, (bytes, bytearray)):
                    image_bytes = bytes(maybe_bytes)
                continue
            if isinstance(item, str):
                user_prompt_parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    user_prompt_parts.append(text)
                continue

        return "", "\n".join(user_prompt_parts), image_bytes

    @staticmethod
    def _extract_output_text(response_json: Dict[str, Any]) -> str:
        output_text = response_json.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        pieces: List[str] = []
        for item in response_json.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                for content in item.get("content", []) or []:
                    if not isinstance(content, dict):
                        continue
                    if content.get("type") in {"output_text", "text"}:
                        text = content.get("text")
                        if isinstance(text, str) and text.strip():
                            pieces.append(text.strip())
            elif item.get("type") in {"output_text", "text"}:
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    pieces.append(text.strip())
        return "\n".join(pieces).strip()

    def generate_content(
        self,
        payload: List[Any],
        generation_config: Optional[Dict[str, Any]] = None,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> _OpenAIResponse:
        system_prompt, user_prompt, image_bytes = self._extract_prompt_parts(payload)
        if not image_bytes:
            raise RuntimeError("OpenAI vision request missing image payload")

        generation_config = generation_config or {}
        response_schema = generation_config.get("response_schema")
        text_format: Dict[str, Any]
        if isinstance(response_schema, dict):
            text_format = {
                "type": "json_schema",
                "name": "ui_detection",
                "strict": True,
                "schema": self._ensure_openai_schema(response_schema),
            }
        else:
            text_format = {"type": "json_object"}

        body: Dict[str, Any] = {
            "model": self.model_name,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": self._image_to_data_url(image_bytes), "detail": "high"},
                        {"type": "input_text", "text": user_prompt},
                    ],
                }
            ],
            "text": {"format": text_format},
            "temperature": float(generation_config.get("temperature", 0.0)),
            "max_output_tokens": int(generation_config.get("max_output_tokens", 4096)),
        }
        if system_prompt.strip():
            body["instructions"] = system_prompt

        timeout = int(max(1.0, float((request_options or {}).get("timeout", self.timeout_seconds))))
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI API error {response.status_code}: {response.text}")

        response_json = response.json()
        text = self._extract_output_text(response_json)
        if not text:
            raise RuntimeError("OpenAI response did not contain output text")
        return _OpenAIResponse(text=text)


class OpenAIVLM(_GeminiVLM):
    """OpenAI semantic VLM adapter with the same JSON output contract."""

    def __init__(self, model_name: str = MODEL_NAME, timeout_seconds: float = 45.0) -> None:
        self.model_name = model_name
        self.timeout_seconds = float(timeout_seconds)

        if not OPENAI_API_KEY:
            raise EnvironmentError(
                "OPEN_API_KEY or OPENAI_API_KEY is not set. Set it in vision/.env before using the vision pipeline."
            )

        self.client = _OpenAIShimClient(OPENAI_API_KEY, self._resolve_model_name(self.model_name), self.timeout_seconds)
        self._genai = _OpenAIShim(self.client)
        self.model_name = self.client.model_name
        logger.info(
            "Initialized OpenAIVLM model=%s timeout_seconds=%.1f",
            self.model_name,
            self.timeout_seconds,
        )

    def _resolve_model_name(self, requested_model: str) -> str:
        requested_model = (requested_model or "").strip() or "gpt-4.1"
        if requested_model.startswith("gpt-") or requested_model.startswith("o"):
            return requested_model
        return "gpt-4.1"

    @staticmethod
    def _system_prompt(image_width: int, image_height: int) -> str:
        prompt = _GeminiVLM._system_prompt(image_width, image_height)
        return prompt.replace("source must be 'gemini_vlm'.", "source must be 'openai_vlm'.")

    @staticmethod
    def _broader_system_prompt(image_width: int, image_height: int) -> str:
        prompt = _GeminiVLM._broader_system_prompt(image_width, image_height)
        return prompt.replace("source must be 'gemini_vlm'.", "source must be 'openai_vlm'.")

    def analyze(self, image_path: str, image_width: int, image_height: int) -> Dict[str, Any]:
        result = super().analyze(image_path, image_width, image_height)
        if isinstance(result, dict):
            for element in result.get("elements", []) or []:
                if isinstance(element, dict):
                    source = str(element.get("source", "")).strip().lower()
                    if not source or source.startswith("gemini") or source.endswith("_enriched"):
                        element["source"] = "openai_vlm"
            if result.get("element_count", 0) != len(result.get("elements", [])):
                result["element_count"] = len(result.get("elements", []))
        return result


class _OpenAIShim:
    """Tiny object exposing the couple of attributes GeminiVLM expects."""

    def __init__(self, client: _OpenAIShimClient) -> None:
        self._client = client

    @staticmethod
    def configure(**_: Any) -> None:
        return None

    @staticmethod
    def list_models() -> list[Any]:
        return []

    def GenerativeModel(self, _: str) -> _OpenAIShimClient:
        return self._client


__all__ = ["OpenAIVLM"]
