# src/perception/grounding/bbox_refiner.py
"""
Refine and validate bounding boxes detected by VLM.
Snaps to edges, resolves partial visibility, and filters noise.
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class EdgeInfo:
    """Information about detected edges."""
    top: int
    bottom: int
    left: int
    right: int
    confidence: float


class BBoxRefiner:
    """Refine VLM bounding boxes using image analysis."""

    def __init__(self, edge_detection_method: str = "canny"):
        """
        Initialize refiner.
        
        Args:
            edge_detection_method: "canny" or "sobel"
        """
        self.edge_detection_method = edge_detection_method

    def denormalize_bbox(self, bbox: Tuple[float, float, float, float], 
                        width: int, height: int) -> Tuple[int, int, int, int]:
        """
        Convert normalized bbox (0-1) to pixel coordinates.
        
        Args:
            bbox: (x_min, y_min, x_max, y_max) in normalized coords
            width: Image width
            height: Image height
        
        Returns:
            (x_min, y_min, x_max, y_max) in pixel coords
        """
        x_min, y_min, x_max, y_max = bbox
        return (
            int(x_min * width),
            int(y_min * height),
            int(x_max * width),
            int(y_max * height)
        )

    def normalize_bbox(self, bbox: Tuple[int, int, int, int],
                      width: int, height: int) -> Tuple[float, float, float, float]:
        """Convert pixel coordinates to normalized bbox."""
        x_min, y_min, x_max, y_max = bbox
        return (
            max(0.0, min(1.0, x_min / width)),
            max(0.0, min(1.0, y_min / height)),
            max(0.0, min(1.0, x_max / width)),
            max(0.0, min(1.0, y_max / height))
        )

    def detect_edges_in_region(self, image: np.ndarray,
                               bbox: Tuple[int, int, int, int],
                               expand_ratio: float = 0.2) -> Optional[EdgeInfo]:
        """
        Detect edges in region around bbox to snap to actual boundaries.
        
        Args:
            image: Input image
            bbox: (x_min, y_min, x_max, y_max) in pixels
            expand_ratio: Expand search region by this ratio
        
        Returns:
            EdgeInfo with snapped boundaries or None
        """
        x_min, y_min, x_max, y_max = bbox
        height, width = image.shape[:2]
        
        # Expand region
        w = x_max - x_min
        h = y_max - y_min
        
        expand_x = int(w * expand_ratio)
        expand_y = int(h * expand_ratio)
        
        x_min = max(0, x_min - expand_x)
        y_min = max(0, y_min - expand_y)
        x_max = min(width, x_max + expand_x)
        y_max = min(height, y_max + expand_y)
        
        # Extract region
        region = image[y_min:y_max, x_min:x_max]
        if region.size == 0:
            return None
        
        # Convert to grayscale if needed
        if len(region.shape) == 3:
            region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        
        # Detect edges
        if self.edge_detection_method == "canny":
            edges = cv2.Canny(region, 50, 150)
        else:  # sobel
            sobelx = cv2.Sobel(region, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(region, cv2.CV_64F, 0, 1, ksize=3)
            edges = np.sqrt(sobelx**2 + sobely**2).astype(np.uint8)
            edges = cv2.threshold(edges, 50, 255, cv2.THRESH_BINARY)[1]
        
        # Find tight bounding contour
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            # No edges found, return expanded bbox
            return EdgeInfo(y_min, y_max, x_min, x_max, 0.5)
        
        # Get overall contour bounds
        all_points = np.vstack(contours)
        x, y, w, h = cv2.boundingRect(all_points)
        
        # Convert back to image coordinates
        snapped_x_min = x_min + x
        snapped_y_min = y_min + y
        snapped_x_max = x_min + x + w
        snapped_y_max = y_min + y + h
        
        # Ensure valid bounds
        snapped_x_min = max(0, snapped_x_min)
        snapped_y_min = max(0, snapped_y_min)
        snapped_x_max = min(width, snapped_x_max)
        snapped_y_max = min(height, snapped_y_max)
        
        # Calculate confidence based on edge density
        edge_density = np.sum(edges) / edges.size
        confidence = min(1.0, edge_density * 10)
        
        return EdgeInfo(
            top=snapped_y_min,
            bottom=snapped_y_max,
            left=snapped_x_min,
            right=snapped_x_max,
            confidence=confidence
        )

    def snap_to_grid(self, bbox: Tuple[int, int, int, int],
                    grid_size: int = 8) -> Tuple[int, int, int, int]:
        """
        Snap bounding box to nearest grid for alignment.
        Useful for UI elements that often align to pixel grids.
        
        Args:
            bbox: (x_min, y_min, x_max, y_max)
            grid_size: Grid cell size in pixels
        
        Returns:
            Snapped bbox
        """
        x_min, y_min, x_max, y_max = bbox
        
        x_min = (x_min // grid_size) * grid_size
        y_min = (y_min // grid_size) * grid_size
        x_max = ((x_max + grid_size - 1) // grid_size) * grid_size
        y_max = ((y_max + grid_size - 1) // grid_size) * grid_size
        
        return (x_min, y_min, x_max, y_max)

    def refine_bbox(self, image: np.ndarray,
                   bbox_normalized: Tuple[float, float, float, float],
                   use_edge_detection: bool = True,
                   use_grid_snap: bool = False,
                   grid_size: int = 8) -> Tuple[float, float, float, float]:
        """
        Refine normalized bounding box using image analysis.
        
        Args:
            image: Input image (BGR)
            bbox_normalized: (x_min, y_min, x_max, y_max) in 0-1 range
            use_edge_detection: Whether to snap to detected edges
            use_grid_snap: Whether to snap to grid
            grid_size: Grid size if use_grid_snap=True
        
        Returns:
            Refined normalized bbox
        """
        height, width = image.shape[:2]
        
        # Convert to pixel coords
        bbox_px = self.denormalize_bbox(bbox_normalized, width, height)
        x_min, y_min, x_max, y_max = bbox_px
        
        # Ensure valid bounds
        x_min = max(0, x_min)
        y_min = max(0, y_min)
        x_max = min(width, x_max)
        y_max = min(height, y_max)
        
        # Skip if too small
        if (x_max - x_min) < 5 or (y_max - y_min) < 5:
            return bbox_normalized
        
        # Apply edge detection
        if use_edge_detection:
            edge_info = self.detect_edges_in_region(image, (x_min, y_min, x_max, y_max))
            if edge_info:
                x_min, y_min = edge_info.left, edge_info.top
                x_max, y_max = edge_info.right, edge_info.bottom
        
        # Apply grid snapping
        if use_grid_snap:
            x_min, y_min, x_max, y_max = self.snap_to_grid((x_min, y_min, x_max, y_max), grid_size)
        
        # Convert back to normalized
        return self.normalize_bbox((x_min, y_min, x_max, y_max), width, height)

    def validate_bbox(self, bbox: Tuple[float, float, float, float]) -> bool:
        """
        Validate that bbox is reasonable.
        
        Returns:
            True if bbox is valid
        """
        x_min, y_min, x_max, y_max = bbox
        
        # Check bounds
        if not all(0 <= val <= 1 for val in bbox):
            return False
        
        # Check not inverted
        if x_min >= x_max or y_min >= y_max:
            return False
        
        # Check minimum size
        area = (x_max - x_min) * (y_max - y_min)
        if area < 0.0001:  # Less than 0.01% of image
            return False
        
        return True

    def filter_bboxes(self, bboxes: List[Tuple[float, float, float, float]],
                     min_area: float = 0.0001,
                     min_confidence: float = 0.3) -> List[Tuple[float, float, float, float]]:
        """Filter out invalid or too-small bboxes."""
        valid = []
        for bbox in bboxes:
            if not self.validate_bbox(bbox):
                continue
            
            x_min, y_min, x_max, y_max = bbox
            area = (x_max - x_min) * (y_max - y_min)
            
            if area >= min_area:
                valid.append(bbox)
        
        return valid
