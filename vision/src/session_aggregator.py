# src/session_aggregator.py
"""
Session-level aggregation for streaming perception.

Addresses ISSUE 2: instead of writing one JSON per frame, a
SessionAggregator collects every frame result into a single coherent
session document and exposes a ``finalize()`` method that saves and
returns the complete ``session_summary.json``.

Streaming flow::

    aggregator = SessionAggregator(output_dir="runs/")
    aggregator.start()

    for frame_path in capture_stream():
        result = pipeline.process_image(frame_path)
        aggregator.append_frame(frame_path, result)
        if stop_requested:
            break

    session_json = aggregator.finalize()   # saves and returns the document

Data model::

    {
        "session_id":   "a1b2c3d4",
        "mode":         "streaming",
        "started_at":   "2026-02-21T09:00:00",
        "finished_at":  "2026-02-21T09:00:42",
        "screen_count": 5,
        "screens": [
            {
                "screen_index": 0,
                "timestamp":    "2026-02-21T09:00:01",
                "image_path":   "frame_001.png",
                "frame_hash":   "abcdef...",
                "elements":     [...],
                "delta": {                          # optional
                    "added":   [...],
                    "removed": [...],
                    "changed": [...]
                }
            }
        ]
    }
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ElementDelta:
    """Change between consecutive frames for a single element."""
    element_id: str
    change_type: str        # "added" | "removed" | "changed"
    before: Optional[Dict[str, Any]] = None
    after:  Optional[Dict[str, Any]] = None


@dataclass
class FrameDelta:
    """Summary of element changes between two consecutive frames."""
    added:   List[Dict[str, Any]] = field(default_factory=list)
    removed: List[Dict[str, Any]] = field(default_factory=list)
    changed: List[Dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScreenRecord:
    """Perception result for a single frame."""
    screen_index: int
    timestamp:    str
    image_path:   str
    frame_hash:   str
    elements:     List[Dict[str, Any]]
    semantic_state: Optional[Dict[str, Any]] = None
    delta:        Optional[Dict[str, Any]] = None
    event_id:     Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "screen_index":   self.screen_index,
            "timestamp":      self.timestamp,
            "image_path":     self.image_path,
            "frame_hash":     self.frame_hash,
            "elements":       self.elements,
        }
        if self.semantic_state is not None:
            d["semantic_state"] = self.semantic_state
        if self.delta is not None:
            d["delta"] = self.delta
        if self.event_id is not None:
            d["event_id"] = self.event_id
        return d


# ---------------------------------------------------------------------------
# SessionAggregator
# ---------------------------------------------------------------------------

class SessionAggregator:
    """
    Collects per-frame perception results and builds a unified session JSON.

    Parameters
    ----------
    output_dir:
        Directory where ``session_summary.json`` will be written.
    detect_deltas:
        When *True*, compare consecutive frames and record element-level
        changes in each ``ScreenRecord.delta``.
    dedup_frames:
        When *True*, identical consecutive frames (same SHA-256 hash) are
        skipped to avoid storing redundant data.
    """

    def __init__(
        self,
        output_dir: str = "data/sessions",
        detect_deltas: bool = True,
        dedup_frames: bool = True,
    ) -> None:
        self.output_dir    = Path(output_dir)
        self.detect_deltas = detect_deltas
        self.dedup_frames  = dedup_frames

        self._session_id:   Optional[str] = None
        self._started_at:   Optional[str] = None
        self._finished_at:  Optional[str] = None
        self._screens:      List[ScreenRecord] = []
        self._seen_hashes:  set[str] = set()
        self._last_elements: List[Dict[str, Any]] = []
        self._active = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, session_id: Optional[str] = None) -> str:
        """
        Initialise a new session.

        Parameters
        ----------
        session_id:
            Optional caller-supplied ID.  Defaults to an 8-char hex stamp.

        Returns
        -------
        str
            The session ID.
        """
        ts = datetime.now().isoformat()
        self._session_id  = session_id or hashlib.md5(ts.encode()).hexdigest()[:8]
        self._started_at  = ts
        self._finished_at = None
        self._screens.clear()
        self._seen_hashes.clear()
        self._last_elements = []
        self._active = True
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("SessionAggregator started: session_id=%s", self._session_id)
        return self._session_id

    def append_frame(
        self,
        image_path: str,
        pipeline_result: Dict[str, Any],
    ) -> Optional[ScreenRecord]:
        """
        Add a processed frame to the session.

        Parameters
        ----------
        image_path:
            Filesystem path of the source frame.
        pipeline_result:
            The dict returned by
            :py:meth:`IntegratedPerceptionPipeline.process_image`.

        Returns
        -------
        ScreenRecord or None
            *None* is returned when the frame is a duplicate and
            ``dedup_frames`` is enabled.
        """
        if not self._active:
            raise RuntimeError(
                "SessionAggregator.start() must be called before append_frame()."
            )

        # --- frame hash ---
        frame_hash = self._hash_file(image_path)

        # --- deduplication ---
        if self.dedup_frames and frame_hash in self._seen_hashes:
            logger.debug("Duplicate frame skipped: %s (%s)", image_path, frame_hash)
            return None
        self._seen_hashes.add(frame_hash)

        # --- extract elements ---
        elements: List[Dict[str, Any]] = []
        if pipeline_result.get("success"):
            elements = pipeline_result.get("detection", {}).get("elements", [])

        # --- delta detection ---
        delta_dict: Optional[Dict[str, Any]] = None
        if self.detect_deltas and self._last_elements:
            delta = self._compute_delta(self._last_elements, elements)
            if not delta.is_empty():
                delta_dict = delta.to_dict()

        # --- record ---
        record = ScreenRecord(
            screen_index   = len(self._screens),
            timestamp      = datetime.now().isoformat(),
            image_path     = str(image_path),
            frame_hash     = frame_hash,
            elements       = elements,
            semantic_state = pipeline_result.get("semantic_state"),
            delta          = delta_dict,
            event_id       = pipeline_result.get("event_id"),
        )
        self._screens.append(record)
        self._last_elements = elements

        logger.debug(
            "Frame appended: index=%d  elements=%d  hash=%s",
            record.screen_index, len(elements), frame_hash,
        )
        return record

    def finalize(self, save: bool = True) -> Dict[str, Any]:
        """
        Close the session and return (and optionally persist) the aggregated JSON.

        Parameters
        ----------
        save:
            Write ``session_summary.json`` to *output_dir*.

        Returns
        -------
        dict
            Complete session document.
        """
        if not self._active:
            raise RuntimeError(
                "SessionAggregator.start() must be called before finalize()."
            )
        self._finished_at = datetime.now().isoformat()
        self._active = False

        document = self._build_document()

        if save:
            path = self.output_dir / f"session_{self._session_id}_summary.json"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(document, fh, indent=2, default=str)
            logger.info("Session saved: %s  (%d screens)", path, len(self._screens))

        return document

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> Optional[str]:
        """Current session ID (``None`` before ``start()`` is called)."""
        return self._session_id

    @property
    def frame_count(self) -> int:
        """Number of frames accepted so far (duplicates excluded)."""
        return len(self._screens)

    @property
    def is_active(self) -> bool:
        """``True`` if a session is in progress."""
        return self._active

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_document(self) -> Dict[str, Any]:
        return {
            "session_id":   self._session_id,
            "mode":         "streaming",
            "started_at":   self._started_at,
            "finished_at":  self._finished_at,
            "screen_count": len(self._screens),
            "screens":      [s.to_dict() for s in self._screens],
        }

    @staticmethod
    def _hash_file(path: str) -> str:
        """SHA-256 digest of *path*'s raw bytes; returns empty string on error."""
        try:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError as exc:
            logger.warning("Could not hash frame %s: %s", path, exc)
            return ""

    @staticmethod
    def _compute_delta(
        prev_elements: List[Dict[str, Any]],
        curr_elements: List[Dict[str, Any]],
    ) -> FrameDelta:
        """
        Lightweight element-level change detection.

        Elements are matched by ``id``.  An element is "changed" when
        any of its ``type``, ``label``, or ``state`` fields differ
        from the previous frame.
        """
        prev_by_id = {e["id"]: e for e in prev_elements if "id" in e}
        curr_by_id = {e["id"]: e for e in curr_elements if "id" in e}

        prev_ids = set(prev_by_id)
        curr_ids = set(curr_by_id)

        added   = [curr_by_id[i] for i in curr_ids - prev_ids]
        removed = [prev_by_id[i] for i in prev_ids - curr_ids]
        changed: List[Dict[str, Any]] = []

        for eid in prev_ids & curr_ids:
            p, c = prev_by_id[eid], curr_by_id[eid]
            if any(p.get(k) != c.get(k) for k in ("type", "label", "state")):
                changed.append({
                    "id":     eid,
                    "before": {k: p.get(k) for k in ("type", "label", "state")},
                    "after":  {k: c.get(k) for k in ("type", "label", "state")},
                })

        return FrameDelta(added=added, removed=removed, changed=changed)
