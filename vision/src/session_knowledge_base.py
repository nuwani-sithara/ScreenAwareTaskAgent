from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_bbox(bbox: Any) -> Optional[List[float]]:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        return [float(v) for v in bbox]
    except Exception:
        return None


def canonical_element_key(element: Dict[str, Any]) -> str:
    """
    Stable session-scoped element identity.

    Prefer label + type because element IDs can drift between frames when the
    VLM rewrites them. Fall back to the raw ID only when no label exists.
    """
    element_type = _normalize_text(element.get("type"))
    label = _normalize_text(element.get("label"))
    element_id = _normalize_text(element.get("id"))

    if label and element_type:
        return f"{element_type}:{label}"
    if label:
        return f"label:{label}"
    if element_id:
        return f"id:{element_id}"
    return f"type:{element_type or 'unknown'}"


@dataclass
class KnownElement:
    element_key: str
    element_type: str
    label: str
    bbox: Optional[List[float]] = None
    confidence: float = 0.0
    source: str = ""
    first_seen_frame: Optional[str] = None
    last_seen_frame: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    first_seen_index: Optional[int] = None
    last_seen_index: Optional[int] = None
    seen_count: int = 0
    miss_count: int = 0
    stale: bool = False
    cached: bool = False
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data.get("bbox") is not None:
            data["bbox"] = [float(v) for v in data["bbox"]]
        return data


class SessionKnowledgeBase:
    """
    Session-scoped best-known UI element registry.

    Tracks the last reliable detection per logical element and provides a
    fallback snapshot when a later frame misses the same element.
    """

    def __init__(
        self,
        session_id: str,
        stale_after_misses: int = 3,
        confidence_floor: float = 0.40,
        decay_per_miss: float = 0.90,
    ) -> None:
        self.session_id = session_id
        self.stale_after_misses = max(1, int(stale_after_misses))
        self.confidence_floor = max(0.0, min(1.0, float(confidence_floor)))
        self.decay_per_miss = max(0.0, min(1.0, float(decay_per_miss)))

        self.started_at = _utc_now()
        self.updated_at = self.started_at
        self.frame_count = 0
        self.known_elements: Dict[str, KnownElement] = {}
        self.frame_log: List[Dict[str, Any]] = []

    def update(
        self,
        elements: List[Dict[str, Any]],
        frame_name: Optional[str] = None,
        frame_index: Optional[int] = None,
        image_size: Optional[Dict[str, Any]] = None,
        source: str = "vision",
    ) -> Dict[str, Any]:
        """
        Merge a frame's detections into the registry and return a serializable snapshot.
        """
        self.frame_count += 1
        self.updated_at = _utc_now()

        current_keys = set()
        normalized_current: List[Dict[str, Any]] = []

        for element in elements or []:
            if not isinstance(element, dict):
                continue
            key = canonical_element_key(element)
            current_keys.add(key)
            bbox = _normalize_bbox(element.get("bbox") or element.get("frame_bbox"))
            confidence = float(element.get("confidence", 0.0) or 0.0)
            label = str(element.get("label") or "").strip()
            element_type = str(element.get("type") or "").strip()
            record = self.known_elements.get(key)
            event = {
                "frame_name": frame_name,
                "frame_index": frame_index,
                "seen_at": self.updated_at,
                "confidence": confidence,
            }

            if record is None:
                record = KnownElement(
                    element_key=key,
                    element_type=element_type,
                    label=label,
                    bbox=bbox,
                    confidence=confidence,
                    source=str(element.get("source") or source),
                    first_seen_frame=frame_name,
                    last_seen_frame=frame_name,
                    first_seen_at=self.updated_at,
                    last_seen_at=self.updated_at,
                    first_seen_index=frame_index,
                    last_seen_index=frame_index,
                    seen_count=1,
                    miss_count=0,
                    stale=False,
                    cached=False,
                    history=[event],
                )
                self.known_elements[key] = record
            else:
                record.element_type = element_type or record.element_type
                record.label = label or record.label
                if bbox is not None:
                    if record.bbox is None or confidence >= record.confidence:
                        record.bbox = bbox
                if confidence >= record.confidence or record.confidence <= 0.0:
                    record.confidence = confidence
                if element.get("source"):
                    record.source = str(element.get("source"))
                record.last_seen_frame = frame_name
                record.last_seen_at = self.updated_at
                record.last_seen_index = frame_index
                record.seen_count += 1
                record.miss_count = 0
                record.stale = False
                record.cached = False
                record.history.append(event)

            normalized = dict(element)
            normalized["session_memory_key"] = key
            normalized["cached"] = False
            normalized_current.append(normalized)

        for key, record in self.known_elements.items():
            if key in current_keys:
                continue
            record.miss_count += 1
            record.cached = True
            if record.miss_count >= self.stale_after_misses:
                record.stale = True
            if record.bbox is not None and record.confidence > 0.0:
                record.confidence = max(
                    self.confidence_floor,
                    round(record.confidence * self.decay_per_miss, 4),
                )

        self.frame_log.append(
            {
                "frame_name": frame_name,
                "frame_index": frame_index,
                "seen_at": self.updated_at,
                "element_count": len(normalized_current),
            }
        )

        return self.snapshot(
            image_size=image_size,
            frame_name=frame_name,
            frame_index=frame_index,
            current_elements=normalized_current,
        )

    def resolve_elements(self, current_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Return current detections plus non-stale cached elements not present in
        the current frame.
        """
        resolved: List[Dict[str, Any]] = []
        current_keys = set()

        for element in current_elements or []:
            if not isinstance(element, dict):
                continue
            key = canonical_element_key(element)
            current_keys.add(key)
            enriched = dict(element)
            enriched["session_memory_key"] = key
            enriched["cached"] = False
            resolved.append(enriched)

        for key, record in self.known_elements.items():
            if key in current_keys or record.stale or record.bbox is None:
                continue
            cached = {
                "id": f"memory_{key}",
                "type": record.element_type,
                "label": record.label,
                "description": "Cached from an earlier frame in the same session",
                "state": "cached",
                "bbox": [float(v) for v in record.bbox],
                "confidence": round(record.confidence, 4),
                "source": record.source or "session_memory",
                "last_seen_frame": record.last_seen_frame,
                "last_seen_index": record.last_seen_index,
                "stale": True,
                "cached": True,
                "session_memory_key": key,
            }
            resolved.append(cached)

        return resolved

    def snapshot(
        self,
        image_size: Optional[Dict[str, Any]] = None,
        frame_name: Optional[str] = None,
        frame_index: Optional[int] = None,
        current_elements: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        resolved_current = current_elements or []
        resolved_elements = self.resolve_elements(resolved_current) if current_elements is not None else []
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "stale_after_misses": self.stale_after_misses,
            "confidence_floor": self.confidence_floor,
            "decay_per_miss": self.decay_per_miss,
            "frame_count": self.frame_count,
            "frame_name": frame_name,
            "frame_index": frame_index,
            "image_size": image_size,
            "known_elements": {
                key: record.to_dict() for key, record in self.known_elements.items()
            },
            "resolved_elements": resolved_elements,
            "current_elements": resolved_current,
        }
