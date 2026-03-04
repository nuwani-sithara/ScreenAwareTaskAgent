"""Base interface for vision-language model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseVLM(ABC):
    """Abstract interface for semantic VLM providers."""

    @abstractmethod
    def analyze(self, image_path: str, image_width: int, image_height: int) -> Dict[str, Any]:
        """Analyze a screenshot and return structured interactive UI detections."""
        raise NotImplementedError
