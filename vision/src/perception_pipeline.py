# src/perception_pipeline.py
"""
Integrated perception pipeline combining capture → perception → interpretation.

This replaces the old YOLO-only pipeline with a hybrid VLM + optional YOLO system.

Usage:
    python src/perception_pipeline.py --image path/to/image.jpg --provider claude
"""

import os
import sys
import argparse
import json
import cv2
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from perception import PerceptionRouter, FeedbackLogger
from interpretation.semantic_state_builder import SemanticStateBuilder


class IntegratedPerceptionPipeline:
    """Main perception pipeline."""

    def __init__(self,
                 vlm_provider: str = "claude",
                 yolo_model_path: Optional[str] = None,
                 use_vlm: bool = True,
                 use_yolo: bool = True):
        """
        Initialize pipeline.
        
        Args:
            vlm_provider: VLM provider ("claude", "gpt4v", "local")
            yolo_model_path: Path to YOLO model
            use_vlm: Enable VLM
            use_yolo: Enable YOLO fast-path
        """
        self.router = PerceptionRouter(
            vlm_provider=vlm_provider,
            yolo_model_path=yolo_model_path,
            use_vlm=use_vlm,
            use_yolo=use_yolo
        )
        self.state_builder = SemanticStateBuilder()
        self.feedback_logger = FeedbackLogger()

    def process_image(self, image_path: str,
                     strategy: str = "hybrid",
                     refine: bool = True,
                     save_output: bool = True) -> Dict:
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
            refine=refine
        )
        
        if not detection_result.parse_successful:
            print(f"ERROR: Detection failed: {detection_result.parse_error}")
            return {
                "success": False,
                "error": detection_result.parse_error
            }
        
        print(f"✓ Detected {len(detection_result.elements)} UI elements")
        for elem in detection_result.elements[:5]:  # Show first 5
            print(f"  - {elem.type}: '{elem.label}' (conf: {elem.confidence:.2f})")
        if len(detection_result.elements) > 5:
            print(f"  ... and {len(detection_result.elements) - 5} more")
        
        # Step 2: Build semantic state
        print("\n[2/3] Building semantic state...")
        semantic_state = self.state_builder.build_semantic_state(detection_result.elements)
        print(f"✓ State built with {semantic_state['summary']['total_elements']} elements")
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
                "refine": refine
            }
        )
        print(f"✓ Event logged: {event_id}")
        
        # Prepare output
        output = {
            "success": True,
            "image_path": str(image_path),
            "event_id": event_id,
            "detection": {
                "num_elements": len(detection_result.elements),
                "elements": [elem.to_dict() for elem in detection_result.elements],
                "parse_successful": detection_result.parse_successful
            },
            "semantic_state": semantic_state
        }
        
        # Save output files
        if save_output:
            self._save_output(image_path, output, detection_result)
        
        return output

    def _save_output(self, image_path: str, output: Dict, detection_result):
        """Save detection and state results to files."""
        base_name = Path(image_path).stem
        base_dir = Path(image_path).parent
        
        # Save JSON output
        json_path = base_dir / f"{base_name}_perception_output.json"
        with open(json_path, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        print(f"  Saved: {json_path}")
        
        # Save annotated image
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
            "button": (0, 255, 0),      # Green
            "input_field": (255, 0, 0), # Blue
            "text": (0, 255, 255),      # Yellow
            "icon": (255, 0, 255),      # Magenta
        }
        
        for elem in elements:
            x_min, y_min, x_max, y_max = elem.bbox
            x_min = int(x_min * width)
            y_min = int(y_min * height)
            x_max = int(x_max * width)
            y_max = int(y_max * height)
            
            color = colors.get(elem.type, (255, 255, 255))
            
            # Draw rectangle
            cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, 2)
            
            # Draw label
            label = f"{elem.type} ({elem.confidence:.2f})"
            cv2.putText(
                image,
                label,
                (x_min, max(y_min - 5, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )
        
        return image

    def save_feedback(self, event_id: str, success: bool, reason: Optional[str] = None):
        """Record feedback for detection event."""
        self.feedback_logger.mark_feedback(event_id, success, reason)
        print(f"\n✓ Feedback recorded: {'SUCCESS' if success else 'FAILURE'}")
        if reason:
            print(f"  Reason: {reason}")

    def get_statistics(self) -> Dict:
        """Get detection statistics."""
        return self.feedback_logger.get_improvement_summary()


def main():
    parser = argparse.ArgumentParser(
        description="Integrated UI perception pipeline with VLM support."
    )
    parser.add_argument("--image", required=True, help="Path to image")
    parser.add_argument(
        "--provider",
        default="claude",
        choices=["claude", "gpt4v", "local"],
        help="VLM provider"
    )
    parser.add_argument(
        "--strategy",
        default="hybrid",
        choices=["vlm", "yolo", "hybrid"],
        help="Detection strategy"
    )
    parser.add_argument("--yolo-model", help="Path to YOLO model")
    parser.add_argument("--no-refine", action="store_true", help="Skip refinement")
    parser.add_argument("--no-save", action="store_true", help="Don't save outputs")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = IntegratedPerceptionPipeline(
        vlm_provider=args.provider,
        yolo_model_path=args.yolo_model
    )
    
    # Show statistics if requested
    if args.stats:
        stats = pipeline.get_statistics()
        print("\nPerception Statistics:")
        print(json.dumps(stats, indent=2, default=str))
        return
    
    # Process image
    if not os.path.exists(args.image):
        print(f"ERROR: Image not found: {args.image}")
        sys.exit(1)
    
    result = pipeline.process_image(
        args.image,
        strategy=args.strategy,
        refine=not args.no_refine,
        save_output=not args.no_save
    )
    
    if result["success"]:
        print("\n✓ Pipeline completed successfully!")
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n✗ Pipeline failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    from typing import Optional, Dict
    main()
