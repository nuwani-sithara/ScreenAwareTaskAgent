# src/perception/perception_router.py
"""
Main perception pipeline router.
Decides between VLM (zero-shot), YOLO (fast-path), or hybrid approaches.
"""

import os
import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path

from .vlm import VLMClient, UIElement, UIAnalysisResult, get_vlm_client
from .grounding import BBoxRefiner, OverlapResolver


class PerceptionRouter:
    """
    Route UI detection requests through optimal pipeline.
    
    Strategy:
    1. If element type is known → try YOLO first
    2. If YOLO confidence is high → use YOLO result
    3. Otherwise → use VLM (zero-shot)
    4. Refine results with grounding layer
    """

    def __init__(self,
                 vlm_provider: str = "claude",
                 yolo_model_path: Optional[str] = None,
                 use_vlm: bool = True,
                 use_yolo: bool = True,
                 vlm_kwargs: Optional[Dict] = None):
        """
        Initialize perception router.
        
        Args:
            vlm_provider: "claude", "gpt4v", "local"
            yolo_model_path: Path to YOLO model weights
            use_vlm: Enable VLM-based detection
            use_yolo: Enable YOLO-based detection
            vlm_kwargs: Additional VLM configuration
        """
        self.vlm_provider = vlm_provider
        self.use_vlm = use_vlm
        self.use_yolo = use_yolo
        self.yolo_model_path = yolo_model_path
        
        # Initialize components
        self.vlm_client: Optional[VLMClient] = None
        self.yolo_model = None
        self.bbox_refiner = BBoxRefiner()
        self.overlap_resolver = OverlapResolver()
        
        # Initialize VLM if enabled
        if self.use_vlm:
            try:
                vlm_kwargs = vlm_kwargs or {}
                self.vlm_client = get_vlm_client(vlm_provider, **vlm_kwargs)
            except Exception as e:
                print(f"Warning: Failed to initialize VLM client: {e}")
                self.use_vlm = False
        
        # Initialize YOLO if enabled
        if self.use_yolo and yolo_model_path:
            try:
                from ultralytics import YOLO
                self.yolo_model = YOLO(yolo_model_path)
            except Exception as e:
                print(f"Warning: Failed to load YOLO model: {e}")
                self.use_yolo = False

    def detect_with_yolo(self, image_path: str,
                        conf_threshold: float = 0.5,
                        iou_threshold: float = 0.5) -> UIAnalysisResult:
        """
        Detect UI elements using YOLO (fast-path).
        
        Args:
            image_path: Path to image
            conf_threshold: Confidence threshold
            iou_threshold: NMS IOU threshold
        
        Returns:
            UIAnalysisResult
        """
        if not self.yolo_model:
            raise RuntimeError("YOLO model not initialized")
        
        try:
            # Read image to get dimensions
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Failed to read image: {image_path}")
            
            height, width = img.shape[:2]
            
            # Run YOLO inference
            results = self.yolo_model.predict(image_path, conf=conf_threshold, iou=iou_threshold)[0]
            
            # Convert YOLO detections to UIElements
            elements = []
            for idx, (box, cls, conf) in enumerate(zip(results.boxes.xyxy, results.boxes.cls, results.boxes.conf)):
                x_min, y_min, x_max, y_max = box.tolist()
                
                # Normalize to 0-1
                bbox_norm = (
                    x_min / width,
                    y_min / height,
                    x_max / width,
                    y_max / height
                )
                
                element = UIElement(
                    id=f"yolo_{idx}",
                    type=self.yolo_model.names[int(cls)],
                    label=self.yolo_model.names[int(cls)],
                    description=f"YOLO detected: {self.yolo_model.names[int(cls)]}",
                    state="detected",
                    bbox=bbox_norm,
                    confidence=float(conf)
                )
                elements.append(element)
            
            return UIAnalysisResult(
                elements=elements,
                parse_successful=True,
                raw_response=f"YOLO detection: {len(elements)} elements"
            )
        
        except Exception as e:
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error=f"YOLO detection error: {str(e)}"
            )

    def detect_with_vlm(self, image_path: str,
                       prompt: Optional[str] = None) -> UIAnalysisResult:
        """
        Detect UI elements using VLM (zero-shot).
        
        Args:
            image_path: Path to image
            prompt: Custom prompt (optional)
        
        Returns:
            UIAnalysisResult
        """
        if not self.vlm_client:
            raise RuntimeError("VLM client not initialized")
        
        return self.vlm_client.analyze_ui(image_path, prompt)

    def refine_detections(self, image_path: str,
                         result: UIAnalysisResult,
                         use_edge_snap: bool = True,
                         resolve_overlaps: bool = True,
                         overlap_threshold: float = 0.3) -> UIAnalysisResult:
        """
        Refine detected elements using grounding layer.
        
        Args:
            image_path: Path to image
            result: Initial detection result
            use_edge_snap: Snap bboxes to detected edges
            resolve_overlaps: Merge overlapping detections
            overlap_threshold: IoU threshold for overlap resolution
        
        Returns:
            Refined UIAnalysisResult
        """
        if not result.elements:
            return result
        
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                return result
            
            # Refine each bbox
            refined_elements = []
            bboxes_list = []
            ids_list = []
            
            for elem in result.elements:
                # Refine bbox using edge detection
                if use_edge_snap:
                    refined_bbox = self.bbox_refiner.refine_bbox(
                        image,
                        elem.bbox,
                        use_edge_detection=True,
                        use_grid_snap=False
                    )
                else:
                    refined_bbox = elem.bbox
                
                # Validate
                if self.bbox_refiner.validate_bbox(refined_bbox):
                    elem.bbox = refined_bbox
                    refined_elements.append(elem)
                    bboxes_list.append(refined_bbox)
                    ids_list.append(elem.id)
            
            # Resolve overlaps
            if resolve_overlaps and len(refined_elements) > 1:
                resolved_bboxes, resolved_ids = self.overlap_resolver.resolve_overlaps(
                    bboxes_list,
                    ids_list,
                    iou_threshold=overlap_threshold,
                    strategy="merge"
                )
                
                # Update elements with resolved bboxes
                id_to_elem = {elem.id: elem for elem in refined_elements}
                refined_elements = []
                for bbox, elem_id in zip(resolved_bboxes, resolved_ids):
                    if elem_id in id_to_elem:
                        elem = id_to_elem[elem_id]
                        elem.bbox = bbox
                        refined_elements.append(elem)
            
            # Filter nested elements
            bboxes_list = [elem.bbox for elem in refined_elements]
            ids_list = [elem.id for elem in refined_elements]
            
            if len(bboxes_list) > 1:
                filtered_bboxes, filtered_ids = self.overlap_resolver.filter_nested(
                    bboxes_list,
                    ids_list,
                    nesting_threshold=0.8
                )
                
                id_set = set(filtered_ids)
                refined_elements = [elem for elem in refined_elements if elem.id in id_set]
            
            return UIAnalysisResult(
                elements=refined_elements,
                page_structure=result.page_structure,
                parse_successful=True,
                raw_response=result.raw_response
            )
        
        except Exception as e:
            print(f"Warning: Refinement failed: {e}")
            return result

    def detect(self, image_path: str,
              strategy: str = "hybrid",
              vlm_prompt: Optional[str] = None,
              yolo_conf: float = 0.5,
              refine: bool = True,
              min_vlm_confidence: float = 0.5) -> UIAnalysisResult:
        """
        Main detection method.
        
        Args:
            image_path: Path to image
            strategy: "vlm" (VLM only), "yolo" (YOLO only), "hybrid"
            vlm_prompt: Custom VLM prompt
            yolo_conf: YOLO confidence threshold
            refine: Whether to refine detections
            min_vlm_confidence: Minimum confidence for VLM results
        
        Returns:
            UIAnalysisResult with detected UI elements
        """
        if not os.path.exists(image_path):
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error=f"Image not found: {image_path}"
            )
        
        result = None
        
        # Execute strategy
        if strategy == "vlm" and self.use_vlm:
            result = self.detect_with_vlm(image_path, vlm_prompt)
        
        elif strategy == "yolo" and self.use_yolo:
            result = self.detect_with_yolo(image_path, conf_threshold=yolo_conf)
        
        elif strategy == "hybrid":
            # Try YOLO first (faster)
            if self.use_yolo:
                result = self.detect_with_yolo(image_path, conf_threshold=yolo_conf)
                
                # If YOLO results are good, use them
                if result.elements and any(e.confidence >= min_vlm_confidence for e in result.elements):
                    pass  # Use YOLO results
                else:
                    # Fall back to VLM
                    if self.use_vlm:
                        result = self.detect_with_vlm(image_path, vlm_prompt)
            else:
                # YOLO disabled, use VLM
                if self.use_vlm:
                    result = self.detect_with_vlm(image_path, vlm_prompt)
        
        if result is None:
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error="Detection failed: no valid strategy or model"
            )
        
        # Refine detections
        if refine and result.elements:
            result = self.refine_detections(image_path, result)
        
        return result

    def detect_changes(self, image_path_1: str, image_path_2: str,
                      strategy: str = "hybrid") -> Dict[str, Any]:
        """
        Compare two UI screenshots and detect changes.
        
        Args:
            image_path_1: First image
            image_path_2: Second image
            strategy: Detection strategy
        
        Returns:
            Dict with added, removed, changed elements
        """
        result1 = self.detect(image_path_1, strategy=strategy)
        result2 = self.detect(image_path_2, strategy=strategy)
        
        # Simple comparison based on element types
        types1 = {elem.type for elem in result1.elements}
        types2 = {elem.type for elem in result2.elements}
        
        return {
            "added": list(types2 - types1),
            "removed": list(types1 - types2),
            "elements_1": result1.elements,
            "elements_2": result2.elements
        }
