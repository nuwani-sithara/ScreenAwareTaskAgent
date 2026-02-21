# src/perception/feedback_logger.py
"""
Weak supervision feedback logging.
Store successful detections to build self-improving dataset.

Additions (streaming / session support):
- log_streaming_event()  : lightweight per-frame entry during streaming
- log_session_summary()  : persist the final SessionAggregator document
- log_vlm_batch_result() : record batch-classification outcomes for quality tracking
"""

import json
import logging
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import hashlib

from .vlm import UIElement

_log = logging.getLogger(__name__)


class FeedbackLogger:
    """
    Log and store successful UI detections for weak supervision.
    
    This enables a weak self-improvement loop:
    1. VLM detects UI elements
    2. Agent acts based on detection
    3. If action succeeds → store as positive example
    4. If action fails → store as negative example
    5. Use these to fine-tune or validate future detections
    """

    def __init__(self, feedback_dir: Optional[str] = None):
        """
        Initialize feedback logger.
        
        Args:
            feedback_dir: Directory to store feedback logs
                         Default: data/feedback/
        """
        if feedback_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            feedback_dir = os.path.join(base_dir, "data", "feedback")
        
        self.feedback_dir = feedback_dir
        os.makedirs(feedback_dir, exist_ok=True)
        
        # Subdirectories
        self.positive_dir = os.path.join(feedback_dir, "positive")
        self.negative_dir = os.path.join(feedback_dir, "negative")
        self.session_dir = os.path.join(feedback_dir, "sessions")
        
        os.makedirs(self.positive_dir, exist_ok=True)
        os.makedirs(self.negative_dir, exist_ok=True)
        os.makedirs(self.session_dir, exist_ok=True)
        
        self.current_session_id = self._generate_session_id()
        self.current_session_log = []

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]

    def log_detection(self,
                     image_path: str,
                     elements: List[UIElement],
                     action: Optional[str] = None,
                     target_element_id: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> str:
        """
        Log a detection event.
        
        Args:
            image_path: Path to image
            elements: Detected UI elements
            action: Action taken (e.g., "click", "type", "scroll")
            target_element_id: ID of element that was interacted with
            metadata: Additional metadata
        
        Returns:
            Event ID
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "image_path": str(image_path),
            "elements": [elem.to_dict() for elem in elements],
            "action": action,
            "target_element_id": target_element_id,
            "metadata": metadata or {}
        }
        
        self.current_session_log.append(event)
        
        return hashlib.md5(str(event).encode()).hexdigest()[:16]

    def mark_feedback(self,
                     event_id: str,
                     success: bool,
                     reason: Optional[str] = None,
                     confidence_adjustment: float = 0.0):
        """
        Mark feedback for a detection event.
        
        Args:
            event_id: Event ID from log_detection
            success: Whether action succeeded
            reason: Reason for success/failure
            confidence_adjustment: Adjust element confidence based on feedback
        """
        feedback_data = {
            "event_id": event_id,
            "success": success,
            "reason": reason or "",
            "confidence_adjustment": confidence_adjustment,
            "timestamp": datetime.now().isoformat()
        }
        
        # Determine directory
        target_dir = self.positive_dir if success else self.negative_dir
        
        # Save feedback
        feedback_path = os.path.join(
            target_dir,
            f"{event_id}_{datetime.now().timestamp()}.json"
        )
        
        with open(feedback_path, 'w') as f:
            json.dump(feedback_data, f, indent=2)

    def save_session(self) -> str:
        """
        Save current session log.
        
        Returns:
            Path to session file
        """
        session_path = os.path.join(
            self.session_dir,
            f"session_{self.current_session_id}_{datetime.now().timestamp()}.json"
        )
        
        with open(session_path, 'w') as f:
            json.dump(self.current_session_log, f, indent=2)
        
        self.current_session_log = []
        return session_path

    def get_successful_detections(self,
                                 element_type: Optional[str] = None,
                                 limit: Optional[int] = None) -> List[Dict]:
        """
        Get successful detections from feedback logs.
        
        Args:
            element_type: Filter by element type (optional)
            limit: Max results to return
        
        Returns:
            List of successful detection records
        """
        successful = []
        
        for filename in os.listdir(self.positive_dir):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(self.positive_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    record = json.load(f)
                    successful.append(record)
            except:
                continue
        
        if element_type:
            successful = [r for r in successful if element_type in str(r)]
        
        if limit:
            successful = successful[:limit]
        
        return successful

    def get_failed_detections(self,
                            element_type: Optional[str] = None,
                            limit: Optional[int] = None) -> List[Dict]:
        """Get failed detections from feedback logs."""
        failed = []
        
        for filename in os.listdir(self.negative_dir):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(self.negative_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    record = json.load(f)
                    failed.append(record)
            except:
                continue
        
        if element_type:
            failed = [r for r in failed if element_type in str(r)]
        
        if limit:
            failed = failed[:limit]
        
        return failed

    def get_element_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about detected elements from successful feedback.
        
        Returns:
            Dict with element type statistics
        """
        successful = self.get_successful_detections()
        
        type_counts = {}
        type_confidence = {}
        
        for record in successful:
            for elem_data in record.get("elements", []):
                elem_type = elem_data.get("type", "unknown")
                conf = elem_data.get("confidence", 0.5)
                
                if elem_type not in type_counts:
                    type_counts[elem_type] = 0
                    type_confidence[elem_type] = []
                
                type_counts[elem_type] += 1
                type_confidence[elem_type].append(conf)
        
        # Calculate averages
        stats = {}
        for elem_type, count in type_counts.items():
            confidences = type_confidence[elem_type]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            
            stats[elem_type] = {
                "count": count,
                "avg_confidence": avg_conf,
                "min_confidence": min(confidences) if confidences else 0,
                "max_confidence": max(confidences) if confidences else 1
            }
        
        return stats

    def export_training_dataset(self,
                               output_path: Optional[str] = None,
                               min_confidence: float = 0.7) -> str:
        """
        Export successful detections as potential training dataset.
        
        Args:
            output_path: Output file path
            min_confidence: Minimum confidence threshold
        
        Returns:
            Path to exported dataset
        """
        if output_path is None:
            output_path = os.path.join(
                self.feedback_dir,
                f"training_dataset_{datetime.now().timestamp()}.json"
            )
        
        successful = self.get_successful_detections()
        
        # Filter and prepare for training
        training_data = []
        for record in successful:
            filtered_elements = [
                elem for elem in record.get("elements", [])
                if elem.get("confidence", 0.5) >= min_confidence
            ]
            
            if filtered_elements:
                training_data.append({
                    "image_path": record.get("image_path"),
                    "elements": filtered_elements,
                    "success": True
                })
        
        with open(output_path, 'w') as f:
            json.dump(training_data, f, indent=2)
        
        return output_path

    def get_improvement_summary(self) -> Dict[str, Any]:
        """Get summary of detection improvements over time."""
        successful = self.get_successful_detections()
        failed = self.get_failed_detections()
        
        total_events = len(successful) + len(failed)
        success_rate = len(successful) / total_events if total_events > 0 else 0
        
        return {
            "total_events": total_events,
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": success_rate,
            "element_types_seen": list(set(
                elem.get("type", "unknown")
                for record in successful + failed
                for elem in record.get("elements", [])
            )),
            "stats": self.get_element_statistics()
        }

    # ------------------------------------------------------------------
    # Streaming / session helpers
    # ------------------------------------------------------------------

    def log_streaming_event(
        self,
        session_id: str,
        frame_index: int,
        image_path: str,
        elements: List[UIElement],
        delta: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log a single streaming frame as a lightweight event.

        Parameters
        ----------
        session_id:   Streaming session identifier.
        frame_index:  Zero-based index of this frame within the session.
        image_path:   Filesystem path of the captured frame.
        elements:     UI elements detected in this frame.
        delta:        Optional change delta relative to the previous frame.
        metadata:     Arbitrary key-value metadata.

        Returns
        -------
        str
            Event ID.
        """
        event: Dict[str, Any] = {
            "event_type":   "streaming_frame",
            "session_id":   session_id,
            "frame_index":  frame_index,
            "timestamp":    datetime.now().isoformat(),
            "image_path":   str(image_path),
            "num_elements": len(elements),
            "elements":     [e.to_dict() for e in elements],
            "metadata":     metadata or {},
        }
        if delta:
            event["delta"] = delta

        self.current_session_log.append(event)
        event_id = hashlib.md5(str(event).encode()).hexdigest()[:16]
        _log.debug(
            "Streaming frame logged: session=%s  frame=%d  elements=%d",
            session_id, frame_index, len(elements),
        )
        return event_id

    def log_session_summary(
        self,
        session_doc: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """
        Persist the final session document produced by
        :class:`~session_aggregator.SessionAggregator`.

        The file is written to ``<feedback_dir>/sessions/`` and can be used
        later for replay, debugging, or training-data extraction.

        Parameters
        ----------
        session_doc:
            The dict returned by ``SessionAggregator.finalize()``.
        filename:
            Override the auto-generated filename.

        Returns
        -------
        str
            Absolute path to the saved file.
        """
        sid = session_doc.get("session_id", "unknown")
        if filename is None:
            filename = f"session_{sid}_{int(datetime.now().timestamp())}.json"

        path = os.path.join(self.session_dir, filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(session_doc, fh, indent=2, default=str)

        _log.info(
            "Session summary logged: %s  screens=%s",
            path, session_doc.get("screen_count", "?"),
        )
        return path

    def log_vlm_batch_result(
        self,
        image_path: str,
        frame_hash: str,
        num_elements_sent: int,
        num_elements_classified: int,
        used_cache: bool,
        used_fallback: bool,
        provider: str = "",
    ) -> None:
        """
        Record the outcome of a VLM batch-classification call.

        Used to monitor hit-rates, fallback frequency, and cache efficiency.

        Parameters
        ----------
        image_path:              Path to the classified frame.
        frame_hash:              SHA-256 hash of the frame.
        num_elements_sent:       Elements sent to the VLM.
        num_elements_classified: Elements successfully classified.
        used_cache:              Whether the result was served from cache.
        used_fallback:           Whether the fallback classifier was invoked.
        provider:                VLM provider name (e.g. "ollama").
        """
        record = {
            "event_type":             "vlm_batch_classification",
            "timestamp":              datetime.now().isoformat(),
            "image_path":             str(image_path),
            "frame_hash":             frame_hash,
            "num_elements_sent":      num_elements_sent,
            "num_elements_classified": num_elements_classified,
            "used_cache":             used_cache,
            "used_fallback":          used_fallback,
            "provider":               provider,
        }
        self.current_session_log.append(record)
        _log.debug(
            "VLM batch: %d/%d classified  cache=%s  fallback=%s  provider=%s",
            num_elements_classified, num_elements_sent,
            used_cache, used_fallback, provider,
        )
