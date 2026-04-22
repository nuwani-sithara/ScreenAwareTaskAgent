"""VLM (Vision-Language Model) integration for UI detection."""

from .vlm_client import VLMClient, GeminiVLMClient, get_vlm_client
from .ui_parser import UIElement, UIAnalysisResult, UIParser
from .prompt_templates import (
    get_ui_discovery_prompt,
    get_element_refinement_prompt,
    get_semantic_state_prompt,
    get_comparison_prompt,
)

__all__ = [
    "VLMClient",
    "GeminiVLMClient",
    "get_vlm_client",
    "UIElement",
    "UIAnalysisResult",
    "UIParser",
    "get_ui_discovery_prompt",
    "get_element_refinement_prompt",
    "get_semantic_state_prompt",
    "get_comparison_prompt",
]
