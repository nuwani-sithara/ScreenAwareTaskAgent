# src/perception/perception_router.py
"""
Main perception pipeline router.
Uses OpenAI VLM for zero-shot detection with optional YOLO fast-path.
"""

import os
import cv2
import numpy as np
import tempfile
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path

from .vlm import (
    VLMClient,
    UIElement,
    UIAnalysisResult,
    get_vlm_client,
    get_ui_discovery_prompt,
)
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
                 vlm_provider: str = "openai",
                 yolo_model_path: Optional[str] = None,
                 use_vlm: bool = True,
                 use_yolo: bool = True,
                 vlm_kwargs: Optional[Dict] = None):
        """
        Initialize perception router.
        
        Args:
            vlm_provider: Must be "openai" or "gemini"
            yolo_model_path: Path to YOLO model weights
            use_vlm: Enable VLM-based detection
            use_yolo: Enable YOLO-based detection
            vlm_kwargs: Additional VLM configuration
        """
        self.vlm_provider = vlm_provider
        self.use_vlm = use_vlm
        self.use_yolo = use_yolo
        self.yolo_model_path = yolo_model_path
        self.vlm_init_error: Optional[str] = None
        self.yolo_init_error: Optional[str] = None
        
        # Initialize components
        self.vlm_client: Optional[VLMClient] = None
        self.yolo_model = None
        self.bbox_refiner = BBoxRefiner()
        self.overlap_resolver = OverlapResolver()
        
        # Initialize VLM if enabled
        if self.use_vlm:
            try:
                if vlm_provider not in {"openai", "gemini"}:
                    raise ValueError(
                        f"Unsupported VLM provider: {vlm_provider!r}. Supported providers are 'openai' and 'gemini'."
                    )
                vlm_kwargs = vlm_kwargs or {}
                self.vlm_client = get_vlm_client(vlm_provider, **vlm_kwargs)
            except Exception as e:
                self.vlm_init_error = str(e)
                print(f"Warning: Failed to initialize VLM client: {self.vlm_init_error}")
                self.use_vlm = False
        
        # Initialize YOLO if enabled
        if self.use_yolo and yolo_model_path:
            try:
                from ultralytics import YOLO
                self.yolo_model = YOLO(yolo_model_path)
            except Exception as e:
                self.yolo_init_error = str(e)
                print(f"Warning: Failed to load YOLO model: {self.yolo_init_error}")
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

    @staticmethod
    def _bbox_iou(b1: Tuple[float, float, float, float],
                  b2: Tuple[float, float, float, float]) -> float:
        x1 = max(b1[0], b2[0])
        y1 = max(b1[1], b2[1])
        x2 = min(b1[2], b2[2])
        y2 = min(b1[3], b2[3])
        if x2 <= x1 or y2 <= y1:
            return 0.0
        inter = (x2 - x1) * (y2 - y1)
        a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
        a2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
        denom = a1 + a2 - inter
        return inter / denom if denom > 0 else 0.0

    def _deduplicate_elements(self,
                              elements: List[UIElement],
                              iou_threshold: float = 0.75) -> List[UIElement]:
        if not elements:
            return []

        # Keep highest confidence first.
        sorted_elements = sorted(elements, key=lambda e: e.confidence, reverse=True)
        deduped: List[UIElement] = []

        for cand in sorted_elements:
            is_duplicate = False
            for kept in deduped:
                same_type = cand.type == kept.type
                if same_type and self._bbox_iou(cand.bbox, kept.bbox) >= iou_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                deduped.append(cand)

        return deduped

    def _map_tile_bbox_to_global(self,
                                 tile_bbox: Tuple[float, float, float, float],
                                 x0: int, y0: int,
                                 tile_w: int, tile_h: int,
                                 full_w: int, full_h: int) -> Tuple[float, float, float, float]:
        x_min, y_min, x_max, y_max = tile_bbox
        gx_min = (x0 + (x_min * tile_w)) / full_w
        gy_min = (y0 + (y_min * tile_h)) / full_h
        gx_max = (x0 + (x_max * tile_w)) / full_w
        gy_max = (y0 + (y_max * tile_h)) / full_h

        gx_min, gx_max = sorted((max(0.0, min(1.0, gx_min)), max(0.0, min(1.0, gx_max))))
        gy_min, gy_max = sorted((max(0.0, min(1.0, gy_min)), max(0.0, min(1.0, gy_max))))
        return gx_min, gy_min, gx_max, gy_max

    def detect_with_vlm_multi_pass(self,
                                   image_path: str,
                                   prompt: Optional[str] = None,
                                   use_tiling: bool = True,
                                   tile_grid: Tuple[int, int] = (2, 2)) -> UIAnalysisResult:
        """
        Multi-pass VLM detection: full-image pass plus optional tiled pass.
        Improves recall of small or dense UI elements.
        """
        base_result = self.detect_with_vlm(image_path, prompt)
        if not use_tiling:
            return base_result

        image = cv2.imread(image_path)
        if image is None:
            return base_result

        full_h, full_w = image.shape[:2]
        rows, cols = tile_grid
        if rows <= 1 and cols <= 1:
            return base_result

        combined_elements = list(base_result.elements)
        tile_h = full_h // rows
        tile_w = full_w // cols

        for r in range(rows):
            for c in range(cols):
                x0 = c * tile_w
                y0 = r * tile_h
                x1 = full_w if c == cols - 1 else (c + 1) * tile_w
                y1 = full_h if r == rows - 1 else (r + 1) * tile_h
                tile = image[y0:y1, x0:x1]
                if tile.size == 0:
                    continue

                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tile_path = tmp.name
                try:
                    cv2.imwrite(tile_path, tile)
                    tile_prompt = prompt or get_ui_discovery_prompt(
                        screen_region=f"tile row {r + 1}/{rows}, column {c + 1}/{cols}"
                    )
                    tile_result = self.detect_with_vlm(tile_path, tile_prompt)
                    for elem in tile_result.elements:
                        elem.bbox = self._map_tile_bbox_to_global(
                            elem.bbox, x0, y0, (x1 - x0), (y1 - y0), full_w, full_h
                        )
                        elem.id = f"{elem.id}_tile_{r}_{c}"
                        combined_elements.append(elem)
                finally:
                    if os.path.exists(tile_path):
                        os.remove(tile_path)

        combined_elements = self._deduplicate_elements(combined_elements)
        return UIAnalysisResult(
            elements=combined_elements,
            page_structure=base_result.page_structure,
            parse_successful=base_result.parse_successful,
            parse_error=base_result.parse_error,
            raw_response=base_result.raw_response
        )

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
                    strategy="keep_largest"
                )
                
                # Update elements with resolved bboxes
                id_to_elem = {elem.id: elem for elem in refined_elements}
                refined_elements = []
                for bbox, elem_id in zip(resolved_bboxes, resolved_ids):
                    if elem_id in id_to_elem:
                        elem = id_to_elem[elem_id]
                        elem.bbox = bbox
                        refined_elements.append(elem)
            
            # Preserve nested elements by default for better recall.
            # Many valid UI elements are intentionally nested (icon in button, text in card).
            
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
            result = self.detect_with_vlm_multi_pass(
                image_path=image_path,
                prompt=vlm_prompt,
                use_tiling=True,
                tile_grid=(2, 2),
            )
        
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
                        result = self.detect_with_vlm_multi_pass(
                            image_path=image_path,
                            prompt=vlm_prompt,
                            use_tiling=True,
                            tile_grid=(2, 2),
                        )
            else:
                # YOLO disabled, use VLM
                if self.use_vlm:
                    result = self.detect_with_vlm_multi_pass(
                        image_path=image_path,
                        prompt=vlm_prompt,
                        use_tiling=True,
                        tile_grid=(2, 2),
                    )
        
        if result is None:
            reason = "Detection failed: no valid strategy or model"
            if strategy == "vlm" and not self.use_vlm and self.vlm_init_error:
                reason = f"VLM unavailable: {self.vlm_init_error}"
            elif strategy == "yolo" and not self.use_yolo and self.yolo_init_error:
                reason = f"YOLO unavailable: {self.yolo_init_error}"
            elif strategy == "hybrid":
                messages = []
                if not self.use_yolo and self.yolo_init_error:
                    messages.append(f"YOLO unavailable: {self.yolo_init_error}")
                if not self.use_vlm and self.vlm_init_error:
                    messages.append(f"VLM unavailable: {self.vlm_init_error}")
                if messages:
                    reason = " | ".join(messages)
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error=reason
            )
        
        # Refine detections
        if refine and result.elements:
            result = self.refine_detections(image_path, result)

        # ------------------------------------------------------------------
        # Single-call batch VLM classification (ISSUE 1 fix)
        #
        # After spatial detection (YOLO or VLM discovery), run one VLM call
        # to classify ALL elements. This replaces per-element VLM calls that
        # previously exceeded the model call budget.
        # ------------------------------------------------------------------
        if result.elements and self.vlm_client is not None:
            needs_batch = any(
                e.type in ("unknown", "") or e.confidence < 0.4
                for e in result.elements
            )
            if needs_batch:
                try:
                    result.elements = self.vlm_client.classify_elements_batch(
                        image_path=image_path,
                        elements=result.elements,
                        max_retries=2,
                        timeout_seconds=getattr(self.vlm_client, "timeout_seconds", 60.0),
                    )
                except NotImplementedError:
                    pass   # provider doesn't support batch; keep existing classifications
                except Exception as exc:
                    print(f"Warning: batch classification failed: {exc}")

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
