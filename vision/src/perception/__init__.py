# src/perception/__init__.py
"""
Visual Perception Layer - Generalized UI detection using VLM + optional YOLO fast-path.
"""

from .perception_router import PerceptionRouter
from .feedback_logger import FeedbackLogger
from .vlm import (
    VLMClient,
    ClaudeVLMClient,
    GPT4VClient,
    LocalVLMClient,
    get_vlm_client,
    UIElement,
    UIAnalysisResult,
    UIParser
)
from .grounding import (
    BBoxRefiner,
    OverlapResolver,
    EdgeInfo,
    BBoxGroup
)

__all__ = [
    # Main router
    "PerceptionRouter",
    "FeedbackLogger",
    
    # VLM components
    "VLMClient",
    "ClaudeVLMClient",
    "GPT4VClient",
    "LocalVLMClient",
    "get_vlm_client",
    "UIElement",
    "UIAnalysisResult",
    "UIParser",
    
    # Grounding components
    "BBoxRefiner",
    "OverlapResolver",
    "EdgeInfo",
    "BBoxGroup",
]
