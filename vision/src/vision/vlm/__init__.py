"""VLM provider implementations for the vision subsystem."""

from src.vision.vlm.openai_vlm import OpenAIVLM

GeminiVLM = OpenAIVLM

__all__ = ["OpenAIVLM", "GeminiVLM"]
