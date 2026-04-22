"""Visual Perception Layer - Gemini-only VLM detection with optional YOLO fast-path."""

from .perception_router import PerceptionRouter
from .feedback_logger import FeedbackLogger
from .vlm import (
    VLMClient,
    GeminiVLMClient,
    get_vlm_client,
    UIElement,
    UIAnalysisResult,
    UIParser,
)
from .grounding import (
    BBoxRefiner,
    OverlapResolver,
    EdgeInfo,
    BBoxGroup,
)

__all__ = [
    "PerceptionRouter",
    "FeedbackLogger",
    "VLMClient",
    "GeminiVLMClient",
    "get_vlm_client",
    "UIElement",
    "UIAnalysisResult",
    "UIParser",
    "BBoxRefiner",
    "OverlapResolver",
    "EdgeInfo",
    "BBoxGroup",
]
