# src/perception_pipeline.py
"""
Integrated perception pipeline combining capture → perception → interpretation.

Two pipeline classes are provided:

* :class:`IntegratedPerceptionPipeline`
    Processes individual images through the full pipeline.  Unchanged API.

* :class:`StreamingPerceptionPipeline`
    Wraps the integrated pipeline with a :class:`~session_aggregator.SessionAggregator`
    to collect every frame into a single session-level JSON document.

    Streaming flow::

        pipeline = StreamingPerceptionPipeline(...)
        session_id = pipeline.start_streaming()

        for frame_path in capture_stream():
            pipeline.process_frame(frame_path)

        result = pipeline.stop_streaming()   # returns session_summary dict
"""

import os
import sys
import argparse
import json
import cv2
from typing import Optional, Dict, Any, Iterator
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from perception import PerceptionRouter, FeedbackLogger
from interpretation.semantic_state_builder import SemanticStateBuilder
from session_aggregator import SessionAggregator


class IntegratedPerceptionPipeline:
    """Main perception pipeline."""

    def __init__(
        self,
        vlm_provider: str = "gemini",
        yolo_model_path: Optional[str] = None,
        use_vlm: bool = True,
        use_yolo: bool = True,
        vlm_kwargs: Optional[Dict] = None,
    ):
        """
        Initialize pipeline.

        Args:
            vlm_provider: VLM provider ("gemini" only)
            yolo_model_path: Path to YOLO model
            use_vlm: Enable VLM
            use_yolo: Enable YOLO fast-path
            vlm_kwargs: Additional kwargs for VLM client initialization
        """
        self.router = PerceptionRouter(
            vlm_provider=vlm_provider,
            yolo_model_path=yolo_model_path,
            use_vlm=use_vlm,
            use_yolo=use_yolo,
            vlm_kwargs=vlm_kwargs or {},
        )
        self.state_builder = SemanticStateBuilder()
        self.feedback_logger = FeedbackLogger()

    def process_image(
        self,
        image_path: str,
        strategy: str = "hybrid",
        refine: bool = True,
        save_output: bool = True,
    ) -> Dict:
        """
        Process a single image through full pipeline.

        Args:
            image_path: Path to image
            strategy: Detection strategy ("vlm", "yolo", "hybrid")
            refine: Whether to refine detections
            save_output: Save results to files

        Returns:
            Dict with detection and state information
        """
        print(f"\n{'='*60}")
        print(f"Processing: {image_path}")
        print(f"Strategy: {strategy}")
        print(f"{'='*60}")

        # Step 1: Detect UI elements
        print("\n[1/3] Running perception (VLM/YOLO)...")
        detection_result = self.router.detect(
            image_path,
            strategy=strategy,
            refine=refine,
        )

        if not detection_result.parse_successful:
            print(f"ERROR: Detection failed: {detection_result.parse_error}")
            return {
                "success": False,
                "error": detection_result.parse_error,
            }

        print(f"Detected {len(detection_result.elements)} UI elements")
        for elem in detection_result.elements[:5]:  # Show first 5
            print(f"  - {elem.type}: '{elem.label}' (conf: {elem.confidence:.2f})")
        if len(detection_result.elements) > 5:
            print(f"  ... and {len(detection_result.elements) - 5} more")

        # Step 2: Build semantic state
        print("\n[2/3] Building semantic state...")
        semantic_state = self.state_builder.build_semantic_state(detection_result.elements)
        print(f"State built with {semantic_state['summary']['total_elements']} elements")
        print(f"  - Actionable: {semantic_state['summary']['actionable_elements']}")
        print(f"  - Inputs: {semantic_state['summary']['input_elements']}")
        print(f"  - Displays: {semantic_state['summary']['display_elements']}")

        # Step 3: Log and optionally save
        print("\n[3/3] Logging results...")
        event_id = self.feedback_logger.log_detection(
            image_path=image_path,
            elements=detection_result.elements,
            metadata={
                "strategy": strategy,
                "refine": refine,
            },
        )
        print(f"Event logged: {event_id}")

        output = {
            "success": True,
            "image_path": str(image_path),
            "event_id": event_id,
            "detection": {
                "num_elements": len(detection_result.elements),
                "elements": [elem.to_dict() for elem in detection_result.elements],
                "parse_successful": detection_result.parse_successful,
            },
            "semantic_state": semantic_state,
        }

        if save_output:
            self._save_output(image_path, output, detection_result)

        return output

    def _save_output(self, image_path: str, output: Dict, detection_result):
        """Save detection and state results to files."""
        base_name = Path(image_path).stem
        base_dir = Path(image_path).parent

        json_path = base_dir / f"{base_name}_perception_output.json"
        with open(json_path, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"  Saved: {json_path}")

        try:
            img = cv2.imread(image_path)
            if img is not None:
                annotated_img = self._draw_elements(img, detection_result.elements)
                ann_path = base_dir / f"{base_name}_annotated.jpg"
                cv2.imwrite(str(ann_path), annotated_img)
                print(f"  Saved: {ann_path}")
        except Exception as e:
            print(f"  Warning: Could not save annotated image: {e}")

    @staticmethod
    def _draw_elements(image, elements):
        """Draw detected elements on image."""
        height, width = image.shape[:2]

        colors = {
            "button": (0, 255, 0),
            "input_field": (255, 0, 0),
            "text": (0, 255, 255),
            "icon": (255, 0, 255),
        }

        for elem in elements:
            x_min, y_min, x_max, y_max = elem.bbox
            x_min = int(x_min * width)
            y_min = int(y_min * height)
            x_max = int(x_max * width)
            y_max = int(y_max * height)

            color = colors.get(elem.type, (255, 255, 255))
            cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, 2)

            label = f"{elem.type} ({elem.confidence:.2f})"
            cv2.putText(
                image,
                label,
                (x_min, max(y_min - 5, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

        return image

    def save_feedback(self, event_id: str, success: bool, reason: Optional[str] = None):
        """Record feedback for detection event."""
        self.feedback_logger.mark_feedback(event_id, success, reason)
        print(f"\nFeedback recorded: {'SUCCESS' if success else 'FAILURE'}")
        if reason:
            print(f"  Reason: {reason}")

    def get_statistics(self) -> Dict:
        """Get detection statistics."""
        return self.feedback_logger.get_improvement_summary()


# ---------------------------------------------------------------------------
# Streaming pipeline (ISSUE 2)
# ---------------------------------------------------------------------------

class StreamingPerceptionPipeline:
    """
    Streaming wrapper around :class:`IntegratedPerceptionPipeline`.

    Captures an arbitrary number of frames, processes each one through the
    full perception stack, and accumulates results inside a
    :class:`~session_aggregator.SessionAggregator`.  When the caller invokes
    :py:meth:`stop_streaming` a single ``session_summary.json`` is saved and
    its content is returned to the agent.

    Parameters
    ----------
    vlm_provider, yolo_model_path, use_vlm, use_yolo, vlm_kwargs:
        Forwarded to :class:`IntegratedPerceptionPipeline`.
    session_output_dir:
        Directory where ``session_summary.json`` will be written.
    detect_deltas:
        Enable element-level change detection between consecutive frames.
    dedup_frames:
        Skip frames whose content is identical to a previously seen frame.
    strategy:
        Default detection strategy used for each frame.
    refine:
        Whether to run bbox refinement on each frame.
    """

    def __init__(
        self,
        vlm_provider: str = "gemini",
        yolo_model_path: Optional[str] = None,
        use_vlm: bool = True,
        use_yolo: bool = True,
        vlm_kwargs: Optional[Dict] = None,
        session_output_dir: str = "data/sessions",
        detect_deltas: bool = True,
        dedup_frames: bool = True,
        strategy: str = "hybrid",
        refine: bool = True,
    ) -> None:
        self._inner = IntegratedPerceptionPipeline(
            vlm_provider=vlm_provider,
            yolo_model_path=yolo_model_path,
            use_vlm=use_vlm,
            use_yolo=use_yolo,
            vlm_kwargs=vlm_kwargs,
        )
        self._aggregator = SessionAggregator(
            output_dir=session_output_dir,
            detect_deltas=detect_deltas,
            dedup_frames=dedup_frames,
        )
        self._default_strategy = strategy
        self._default_refine    = refine

    # ------------------------------------------------------------------
    # Streaming lifecycle
    # ------------------------------------------------------------------

    def start_streaming(self, session_id: Optional[str] = None) -> str:
        """
        Begin a new streaming session.

        Returns
        -------
        str
            Session ID (use to correlate logs / output files).
        """
        sid = self._aggregator.start(session_id=session_id)
        print(f"\n[StreamingPipeline] Session started: {sid}")
        return sid

    def process_frame(
        self,
        image_path: str,
        strategy: Optional[str] = None,
        refine: Optional[bool] = None,
        save_individual: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single captured frame and append it to the active session.

        Parameters
        ----------
        image_path:
            Filesystem path to the captured frame.
        strategy:
            Override the default detection strategy for this frame.
        refine:
            Override the default refinement flag for this frame.
        save_individual:
            When *True*, also write per-frame JSON (default: *False*).

        Returns
        -------
        dict or None
            Pipeline result dict, or *None* if the frame was deduplicated.
        """
        if not self._aggregator.is_active:
            raise RuntimeError(
                "Call start_streaming() before process_frame()."
            )

        result = self._inner.process_image(
            image_path=image_path,
            strategy=strategy or self._default_strategy,
            refine=refine if refine is not None else self._default_refine,
            save_output=save_individual,
        )

        record = self._aggregator.append_frame(image_path, result)
        if record is None:
            print(f"  [StreamingPipeline] Duplicate frame skipped: {image_path}")
            return None

        print(
            f"  [StreamingPipeline] Frame {record.screen_index} appended "
            f"({len(record.elements)} elements)"
        )
        return result

    def stop_streaming(self, save: bool = True) -> Dict[str, Any]:
        """
        Finalise the session and return the aggregated JSON.

        Parameters
        ----------
        save:
            Whether to persist ``session_summary.json`` to disk.

        Returns
        -------
        dict
            Complete session document conforming to the schema documented in
            :mod:`session_aggregator`.
        """
        session_doc = self._aggregator.finalize(save=save)
        print(
            f"\n[StreamingPipeline] Session {self._aggregator.session_id} finalised. "
            f"Screens: {session_doc['screen_count']}"
        )
        return session_doc

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def run_from_directory(
        self,
        image_dir: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Process all images in *image_dir* as a single streaming session.

        Parameters
        ----------
        image_dir:
            Directory containing image files.
        session_id:
            Optional explicit session ID.
        **kwargs:
            Forwarded to :py:meth:`process_frame`.

        Returns
        -------
        dict
            Session summary document.
        """
        image_dir_path = Path(image_dir)
        image_paths = sorted(
            p for p in image_dir_path.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        )
        if not image_paths:
            raise FileNotFoundError(f"No images found in {image_dir}")

        self.start_streaming(session_id=session_id)
        for img_path in image_paths:
            self.process_frame(str(img_path), **kwargs)
        return self.stop_streaming()

    @property
    def frame_count(self) -> int:
        """Number of non-duplicate frames captured so far."""
        return self._aggregator.frame_count


def main():
    parser = argparse.ArgumentParser(
        description="Integrated UI perception pipeline with VLM support."
    )
    parser.add_argument("--image", help="Path to image")
    parser.add_argument("--image-dir", help="Directory of images for batch/streaming processing")
    parser.add_argument(
        "--provider",
        default="gemini",
        choices=["gemini"],
        help="VLM provider (Gemini only)",
    )
    parser.add_argument(
        "--strategy",
        default="hybrid",
        choices=["vlm", "yolo", "hybrid"],
        help="Detection strategy",
    )
    parser.add_argument("--yolo-model", help="Path to YOLO model")
    parser.add_argument(
        "--local-model",
        default="llava-hf/llava-1.5-7b-hf",
        help="Legacy option kept for compatibility; ignored.",
    )
    parser.add_argument("--no-refine", action="store_true", help="Skip refinement")
    parser.add_argument("--no-save", action="store_true", help="Don't save per-image outputs")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Process --image-dir as a streaming session (produces session_summary.json)",
    )
    parser.add_argument(
        "--session-output-dir",
        default="data/sessions",
        help="Directory for session_summary.json (streaming mode)",
    )

    args = parser.parse_args()
    vlm_kwargs = None

    # ---- streaming mode ----
    if args.streaming:
        if not args.image_dir:
            print("ERROR: --streaming requires --image-dir")
            sys.exit(1)
        image_dir = Path(args.image_dir)
        if not image_dir.exists():
            print(f"ERROR: Image directory not found: {image_dir}")
            sys.exit(1)
        streaming_pipeline = StreamingPerceptionPipeline(
            vlm_provider=args.provider,
            yolo_model_path=args.yolo_model,
            vlm_kwargs=vlm_kwargs,
            session_output_dir=args.session_output_dir,
            strategy=args.strategy,
            refine=not args.no_refine,
        )
        session_doc = streaming_pipeline.run_from_directory(str(image_dir))
        print("\nSession summary:")
        print(json.dumps(session_doc, indent=2, default=str))
        return

    # ---- single / batch (original behaviour) ----
    pipeline = IntegratedPerceptionPipeline(
        vlm_provider=args.provider,
        yolo_model_path=args.yolo_model,
        vlm_kwargs=vlm_kwargs,
    )

    if args.stats:
        stats = pipeline.get_statistics()
        print("\nPerception Statistics:")
        print(json.dumps(stats, indent=2, default=str))
        return

    if args.image and not args.image_dir:
        if not os.path.exists(args.image):
            print(f"ERROR: Image not found: {args.image}")
            sys.exit(1)
        result = pipeline.process_image(
            args.image,
            strategy=args.strategy,
            refine=not args.no_refine,
            save_output=not args.no_save,
        )
        if result["success"]:
            print("\nPipeline completed successfully!")
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"\nPipeline failed: {result.get('error')}")
            sys.exit(1)
        return

    if args.image_dir:
        image_dir = Path(args.image_dir)
        if not image_dir.exists():
            print(f"ERROR: Image directory not found: {image_dir}")
            sys.exit(1)
        image_paths = sorted(
            p for p in image_dir.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        )
        if not image_paths:
            print(f"ERROR: No images found in {image_dir}")
            sys.exit(1)
        success_count = fail_count = 0
        for image_path in image_paths:
            result = pipeline.process_image(
                str(image_path),
                strategy=args.strategy,
                refine=not args.no_refine,
                save_output=not args.no_save,
            )
            if result.get("success"):
                success_count += 1
            else:
                fail_count += 1
        print(f"\nBatch complete: success={success_count}, failed={fail_count}, "
              f"total={len(image_paths)}")
        return

    print("ERROR: Provide either --image or --image-dir")
    sys.exit(1)
    parser.add_argument("--image", help="Path to image")
    parser.add_argument("--image-dir", help="Directory of images for batch processing")
    parser.add_argument(
        "--provider",
        default="gemini",
        choices=["gemini"],
        help="VLM provider (Gemini only)",
    )
    parser.add_argument(
        "--strategy",
        default="hybrid",
        choices=["vlm", "yolo", "hybrid"],
        help="Detection strategy",
    )
    parser.add_argument("--yolo-model", help="Path to YOLO model")
    parser.add_argument(
        "--local-model",
        default="llava-hf/llava-1.5-7b-hf",
        help="Legacy option kept for compatibility; ignored.",
    )
    parser.add_argument("--no-refine", action="store_true", help="Skip refinement")
    parser.add_argument("--no-save", action="store_true", help="Don't save outputs")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")

    args = parser.parse_args()

    pipeline = IntegratedPerceptionPipeline(
        vlm_provider=args.provider,
        yolo_model_path=args.yolo_model,
        vlm_kwargs=None,
    )

    if args.stats:
        stats = pipeline.get_statistics()
        print("\nPerception Statistics:")
        print(json.dumps(stats, indent=2, default=str))
        return

    if args.image and not args.image_dir:
        if not os.path.exists(args.image):
            print(f"ERROR: Image not found: {args.image}")
            sys.exit(1)

        result = pipeline.process_image(
            args.image,
            strategy=args.strategy,
            refine=not args.no_refine,
            save_output=not args.no_save,
        )

        if result["success"]:
            print("\nPipeline completed successfully!")
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"\nPipeline failed: {result.get('error')}")
            sys.exit(1)
        return

    if args.image_dir:
        image_dir = Path(args.image_dir)
        if not image_dir.exists():
            print(f"ERROR: Image directory not found: {image_dir}")
            sys.exit(1)

        image_paths = sorted(
            p for p in image_dir.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        )

        if not image_paths:
            print(f"ERROR: No images found in {image_dir}")
            sys.exit(1)

        success_count = 0
        fail_count = 0

        for image_path in image_paths:
            result = pipeline.process_image(
                str(image_path),
                strategy=args.strategy,
                refine=not args.no_refine,
                save_output=not args.no_save,
            )
            if result.get("success"):
                success_count += 1
            else:
                fail_count += 1

        print(f"\nBatch complete: success={success_count}, failed={fail_count}, total={len(image_paths)}")
        return

    print("ERROR: Provide either --image or --image-dir")
    sys.exit(1)


if __name__ == "__main__":
    main()
