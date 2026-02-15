# src/perception/grounding/__init__.py
"""Grounding layer for refining and validating UI element bounding boxes."""

from .bbox_refiner import BBoxRefiner, EdgeInfo
from .overlap_resolver import OverlapResolver, BBoxGroup

__all__ = [
    "BBoxRefiner",
    "EdgeInfo",
    "OverlapResolver",
    "BBoxGroup",
]
