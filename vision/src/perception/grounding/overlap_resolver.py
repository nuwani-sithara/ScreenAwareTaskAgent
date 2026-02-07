# src/perception/grounding/overlap_resolver.py
"""
Resolve overlapping bounding boxes and merge duplicates.
Groups overlapping or nearby elements together.
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class BBoxGroup:
    """Group of overlapping or nearby bboxes."""
    bboxes: List[Tuple[float, float, float, float]]
    merged_bbox: Tuple[float, float, float, float]
    overlap_score: float
    element_ids: List[str]


class OverlapResolver:
    """Resolve overlapping bounding boxes."""

    @staticmethod
    def calculate_iou(bbox1: Tuple[float, float, float, float],
                     bbox2: Tuple[float, float, float, float]) -> float:
        """
        Calculate Intersection over Union (IoU) between two bboxes.
        
        Args:
            bbox1, bbox2: (x_min, y_min, x_max, y_max) in 0-1 range
        
        Returns:
            IoU score (0-1)
        """
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # Calculate intersection
        inter_xmin = max(x1_min, x2_min)
        inter_ymin = max(y1_min, y2_min)
        inter_xmax = min(x1_max, x2_max)
        inter_ymax = min(y1_max, y2_max)
        
        if inter_xmax <= inter_xmin or inter_ymax <= inter_ymin:
            return 0.0
        
        inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
        
        # Calculate union
        bbox1_area = (x1_max - x1_min) * (y1_max - y1_min)
        bbox2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = bbox1_area + bbox2_area - inter_area
        
        if union_area == 0:
            return 0.0
        
        return inter_area / union_area

    @staticmethod
    def calculate_distance(bbox1: Tuple[float, float, float, float],
                          bbox2: Tuple[float, float, float, float]) -> float:
        """
        Calculate minimum distance between two bboxes (0 if overlapping).
        
        Returns:
            Distance in normalized coordinates
        """
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # Calculate closest points
        dx = max(x1_min - x2_max, x2_min - x1_max, 0)
        dy = max(y1_min - y2_max, y2_min - y1_max, 0)
        
        return np.sqrt(dx**2 + dy**2)

    @staticmethod
    def merge_bboxes(bboxes: List[Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
        """
        Merge multiple bboxes into their bounding rectangle.
        
        Args:
            bboxes: List of (x_min, y_min, x_max, y_max)
        
        Returns:
            Merged bbox that contains all inputs
        """
        if not bboxes:
            return (0, 0, 1, 1)
        
        x_mins = [b[0] for b in bboxes]
        y_mins = [b[1] for b in bboxes]
        x_maxs = [b[2] for b in bboxes]
        y_maxs = [b[3] for b in bboxes]
        
        return (
            min(x_mins),
            min(y_mins),
            max(x_maxs),
            max(y_maxs)
        )

    def group_overlapping(self, bboxes: List[Tuple[float, float, float, float]],
                         element_ids: Optional[List[str]] = None,
                         iou_threshold: float = 0.3) -> List[BBoxGroup]:
        """
        Group bboxes that overlap or are very close.
        
        Args:
            bboxes: List of normalized bboxes
            element_ids: Corresponding element IDs (optional)
            iou_threshold: IoU threshold for grouping
        
        Returns:
            List of BBoxGroup objects
        """
        if not element_ids:
            element_ids = [f"elem_{i}" for i in range(len(bboxes))]
        
        n = len(bboxes)
        if n == 0:
            return []
        
        # Build adjacency matrix
        assigned = [False] * n
        groups = []
        
        for i in range(n):
            if assigned[i]:
                continue
            
            # Start new group
            group = [i]
            assigned[i] = True
            
            # Find all overlapping bboxes
            for j in range(i + 1, n):
                if assigned[j]:
                    continue
                
                iou = self.calculate_iou(bboxes[i], bboxes[j])
                if iou >= iou_threshold:
                    group.append(j)
                    assigned[j] = True
            
            # Create group
            group_bboxes = [bboxes[idx] for idx in group]
            merged = self.merge_bboxes(group_bboxes)
            
            # Calculate average overlap score
            if len(group) > 1:
                overlap_scores = [
                    self.calculate_iou(bboxes[group[0]], bboxes[idx])
                    for idx in group[1:]
                ]
                avg_overlap = np.mean(overlap_scores)
            else:
                avg_overlap = 0.0
            
            groups.append(BBoxGroup(
                bboxes=group_bboxes,
                merged_bbox=merged,
                overlap_score=avg_overlap,
                element_ids=[element_ids[idx] for idx in group]
            ))
        
        return groups

    def resolve_overlaps(self, bboxes: List[Tuple[float, float, float, float]],
                        element_ids: Optional[List[str]] = None,
                        iou_threshold: float = 0.3,
                        strategy: str = "merge") -> Tuple[List[Tuple[float, float, float, float]], List[str]]:
        """
        Resolve overlapping bboxes.
        
        Args:
            bboxes: List of normalized bboxes
            element_ids: Corresponding element IDs
            iou_threshold: IoU threshold for considering overlap
            strategy: "merge" (keep merged) or "keep_largest" or "keep_all"
        
        Returns:
            (resolved_bboxes, resolved_ids)
        """
        if not element_ids:
            element_ids = [f"elem_{i}" for i in range(len(bboxes))]
        
        groups = self.group_overlapping(bboxes, element_ids, iou_threshold)
        
        resolved_bboxes = []
        resolved_ids = []
        
        for group in groups:
            if strategy == "merge":
                resolved_bboxes.append(group.merged_bbox)
                # Combine IDs
                combined_id = "_".join(group.element_ids)
                resolved_ids.append(combined_id)
            
            elif strategy == "keep_largest":
                if group.bboxes:
                    # Find largest by area
                    areas = [
                        (b[2] - b[0]) * (b[3] - b[1])
                        for b in group.bboxes
                    ]
                    largest_idx = np.argmax(areas)
                    resolved_bboxes.append(group.bboxes[largest_idx])
                    resolved_ids.append(group.element_ids[largest_idx])
            
            elif strategy == "keep_all":
                resolved_bboxes.extend(group.bboxes)
                resolved_ids.extend(group.element_ids)
        
        return resolved_bboxes, resolved_ids

    def filter_nested(self, bboxes: List[Tuple[float, float, float, float]],
                     element_ids: Optional[List[str]] = None,
                     nesting_threshold: float = 0.8) -> Tuple[List[Tuple[float, float, float, float]], List[str]]:
        """
        Remove bboxes that are mostly nested inside others (likely false positives).
        
        Args:
            bboxes: List of normalized bboxes
            element_ids: Corresponding element IDs
            nesting_threshold: If one bbox contains >threshold of another, remove smaller
        
        Returns:
            (filtered_bboxes, filtered_ids)
        """
        if not element_ids:
            element_ids = [f"elem_{i}" for i in range(len(bboxes))]
        
        keep = [True] * len(bboxes)
        
        for i in range(len(bboxes)):
            if not keep[i]:
                continue
            
            for j in range(i + 1, len(bboxes)):
                if not keep[j]:
                    continue
                
                # Check if one is nested in the other
                area_i = (bboxes[i][2] - bboxes[i][0]) * (bboxes[i][3] - bboxes[i][1])
                area_j = (bboxes[j][2] - bboxes[j][0]) * (bboxes[j][3] - bboxes[j][1])
                
                # Check containment
                i_in_j = self._contains(bboxes[j], bboxes[i])
                j_in_i = self._contains(bboxes[i], bboxes[j])
                
                if i_in_j and area_i / area_j < nesting_threshold:
                    keep[i] = False
                elif j_in_i and area_j / area_i < nesting_threshold:
                    keep[j] = False
        
        filtered_bboxes = [b for i, b in enumerate(bboxes) if keep[i]]
        filtered_ids = [id for i, id in enumerate(element_ids) if keep[i]]
        
        return filtered_bboxes, filtered_ids

    @staticmethod
    def _contains(outer: Tuple[float, float, float, float],
                 inner: Tuple[float, float, float, float]) -> bool:
        """Check if outer bbox contains inner bbox."""
        ox_min, oy_min, ox_max, oy_max = outer
        ix_min, iy_min, ix_max, iy_max = inner
        
        return (ox_min <= ix_min and ix_max <= ox_max and
                oy_min <= iy_min and iy_max <= oy_max)

    def cluster_nearby(self, bboxes: List[Tuple[float, float, float, float]],
                      element_ids: Optional[List[str]] = None,
                      distance_threshold: float = 0.1) -> List[BBoxGroup]:
        """
        Group nearby bboxes even if not overlapping.
        Useful for grouping labels with inputs.
        
        Args:
            bboxes: List of normalized bboxes
            element_ids: Corresponding element IDs
            distance_threshold: Maximum distance for grouping
        
        Returns:
            List of BBoxGroup objects
        """
        if not element_ids:
            element_ids = [f"elem_{i}" for i in range(len(bboxes))]
        
        if len(bboxes) == 0:
            return []
        
        # Build distance matrix
        n = len(bboxes)
        assigned = [False] * n
        groups = []
        
        for i in range(n):
            if assigned[i]:
                continue
            
            group = [i]
            assigned[i] = True
            
            for j in range(i + 1, n):
                if assigned[j]:
                    continue
                
                dist = self.calculate_distance(bboxes[i], bboxes[j])
                if dist <= distance_threshold:
                    group.append(j)
                    assigned[j] = True
            
            group_bboxes = [bboxes[idx] for idx in group]
            merged = self.merge_bboxes(group_bboxes)
            
            groups.append(BBoxGroup(
                bboxes=group_bboxes,
                merged_bbox=merged,
                overlap_score=0.0,
                element_ids=[element_ids[idx] for idx in group]
            ))
        
        return groups
