"""
BBox Refinement Module (Generalization Stage)

Purpose:
- Refine coarse bounding boxes from ANY detector (YOLO / VLM / heuristic)
- Snap to visual edges
- Stabilize geometry
- Filter noise
- Output detector-agnostic refined boxes

This module is intentionally detector-independent.
"""

import json
import cv2
import numpy as np
from typing import Tuple, List, Optional
from dataclasses import dataclass
from pathlib import Path


# =========================
# Data Structures
# =========================

@dataclass
class EdgeInfo:
    top: int
    bottom: int
    left: int
    right: int
    confidence: float


# =========================
# BBox Refiner Core
# =========================

class BBoxRefiner:
    """
    Refine bounding boxes using image evidence.
    """

    def __init__(self, edge_detection_method: str = "canny"):
        self.edge_detection_method = edge_detection_method
        self.min_edge_confidence = 0.06

    def _auto_canny(self, gray: np.ndarray) -> np.ndarray:
        median = float(np.median(gray))
        lower = int(max(10, 0.66 * median))
        upper = int(min(240, 1.33 * median + 25))
        return cv2.Canny(gray, lower, max(lower + 1, upper))

    # ---------- Coordinate utils ----------

    def denormalize_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        width: int,
        height: int
    ) -> Tuple[int, int, int, int]:
        x_min, y_min, x_max, y_max = bbox
        return (
            int(x_min * width),
            int(y_min * height),
            int(x_max * width),
            int(y_max * height),
        )

    def normalize_bbox(
        self,
        bbox: Tuple[int, int, int, int],
        width: int,
        height: int
    ) -> Tuple[float, float, float, float]:
        x_min, y_min, x_max, y_max = bbox
        return (
            max(0.0, min(1.0, x_min / width)),
            max(0.0, min(1.0, y_min / height)),
            max(0.0, min(1.0, x_max / width)),
            max(0.0, min(1.0, y_max / height)),
        )

    def dxdy_to_bbox(
        self,
        dxdy: Tuple[float, float, float, float],
        screen_bbox: Tuple[float, float, float, float],
    ) -> Tuple[float, float, float, float]:
        dx1, dy_top, dx2, dy_bottom = dxdy
        sx1, sy1, sx2, sy2 = screen_bbox
        sw = max(1e-9, sx2 - sx1)
        sh = max(1e-9, sy2 - sy1)
        x1 = sx1 + dx1 * sw
        y1 = sy1 + dy_top * sh
        x2 = sx1 + dx2 * sw
        y2 = sy2 - dy_bottom * sh
        return (
            max(0.0, min(1.0, x1)),
            max(0.0, min(1.0, y1)),
            max(0.0, min(1.0, x2)),
            max(0.0, min(1.0, y2)),
        )

    def bbox_to_dxdy(
        self,
        bbox: Tuple[float, float, float, float],
        screen_bbox: Tuple[float, float, float, float],
    ) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = bbox
        sx1, sy1, sx2, sy2 = screen_bbox
        sw = max(1e-9, sx2 - sx1)
        sh = max(1e-9, sy2 - sy1)
        dx1 = (x1 - sx1) / sw
        dy_top = (y1 - sy1) / sh
        dx2 = (x2 - sx1) / sw
        dy_bottom = (sy2 - y2) / sh
        return (
            max(0.0, min(1.0, dx1)),
            max(0.0, min(1.0, dy_top)),
            max(0.0, min(1.0, dx2)),
            max(0.0, min(1.0, dy_bottom)),
        )

    def item_to_bbox(
        self,
        item: dict,
    ) -> Tuple[float, float, float, float]:
        bbox = item.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            return tuple(float(v) for v in bbox)
        dxdy = item.get("dxdy")
        screen_bbox = item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0])
        if isinstance(dxdy, (list, tuple)) and len(dxdy) == 4:
            return self.dxdy_to_bbox(
                tuple(float(v) for v in dxdy),
                tuple(float(v) for v in screen_bbox),
            )
        return (0.0, 0.0, 1.0, 1.0)

    def bbox_to_dxdy_pixels(
        self,
        bbox: Tuple[float, float, float, float],
        screen_bbox: Tuple[float, float, float, float],
        image_width: int,
        image_height: int,
    ) -> Tuple[int, int]:
        """
        DEPRECATED: returns top-left offset from screen edge.
        Use bbox_to_center_pixels() for accurate click coordinates.
        """
        x1, y1, _, _ = bbox
        sx1, sy1, _, _ = screen_bbox
        screen_x1 = sx1 * image_width
        screen_y1 = sy1 * image_height
        elem_x1 = x1 * image_width
        elem_y1 = y1 * image_height
        dx = int(round(max(0.0, elem_x1 - screen_x1)))
        dy = int(round(max(0.0, elem_y1 - screen_y1)))
        return dx, dy

    def bbox_to_center_pixels(
        self,
        bbox: Tuple[float, float, float, float],
        image_width: int,
        image_height: int,
    ) -> Tuple[int, int]:
        """
        Return the CENTER (cx, cy) of the bounding box in full-image pixel
        coordinates.  These are the correct agent click targets (dx, dy).

        Args:
            bbox: Normalised bounding box (x1, y1, x2, y2) in [0, 1].
            image_width:  Full image width in pixels.
            image_height: Full image height in pixels.

        Returns:
            (cx, cy) integer pixel coordinates relative to top-left of full image.
        """
        x1, y1, x2, y2 = bbox
        cx = int(round((x1 + x2) / 2.0 * image_width))
        cy = int(round((y1 + y2) / 2.0 * image_height))
        return cx, cy

    # ---------- Edge detection ----------

    def detect_edges_in_region(
        self,
        image: np.ndarray,
        bbox: Tuple[int, int, int, int],
        expand_ratio: float = 0.15
    ) -> Optional[EdgeInfo]:

        x_min, y_min, x_max, y_max = bbox
        height, width = image.shape[:2]

        w = x_max - x_min
        h = y_max - y_min

        if w <= 0 or h <= 0:
            return None

        expand_x = int(w * expand_ratio)
        expand_y = int(h * expand_ratio)

        x_min = max(0, x_min - expand_x)
        y_min = max(0, y_min - expand_y)
        x_max = min(width, x_max + expand_x)
        y_max = min(height, y_max + expand_y)

        region = image[y_min:y_max, x_min:x_max]
        if region.size == 0:
            return None

        if len(region.shape) == 3:
            region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        region = cv2.GaussianBlur(region, (3, 3), 0)

        if self.edge_detection_method == "canny":
            edge_map = self._auto_canny(region)
        else:
            sobelx = cv2.Sobel(region, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(region, cv2.CV_64F, 0, 1, ksize=3)
            grad = np.sqrt(sobelx ** 2 + sobely ** 2).astype(np.uint8)
            edge_map = cv2.threshold(grad, 40, 255, cv2.THRESH_BINARY)[1]

        text_control_mask = cv2.adaptiveThreshold(
            region,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            17,
            3,
        )

        edges = cv2.bitwise_or(edge_map, text_control_mask)
        edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
            iterations=1,
        )

        non_zero = cv2.findNonZero(edges)
        if non_zero is None:
            return EdgeInfo(y_min, y_max, x_min, x_max, 0.0)

        rx, ry, rw, rh = cv2.boundingRect(non_zero)
        pad = 1
        rx = max(0, rx - pad)
        ry = max(0, ry - pad)
        rw = min(region.shape[1] - rx, rw + 2 * pad)
        rh = min(region.shape[0] - ry, rh + 2 * pad)

        snapped_x_min = max(0, x_min + rx)
        snapped_y_min = max(0, y_min + ry)
        snapped_x_max = min(width, snapped_x_min + rw)
        snapped_y_max = min(height, snapped_y_min + rh)

        edge_density = float(np.sum(edges > 0)) / float(edges.size)
        box_fill = (rw * rh) / float(max(1, region.shape[0] * region.shape[1]))
        confidence = min(1.0, (edge_density * 2.2) + (0.35 * box_fill))

        # Reject degenerate boxes.
        if (snapped_x_max - snapped_x_min) < 3 or (snapped_y_max - snapped_y_min) < 3:
            return EdgeInfo(y_min, y_max, x_min, x_max, 0.0)

        return EdgeInfo(
            top=snapped_y_min,
            bottom=snapped_y_max,
            left=snapped_x_min,
            right=snapped_x_max,
            confidence=confidence,
        )

    # ---------- Grid snapping ----------

    def snap_to_grid(
        self,
        bbox: Tuple[int, int, int, int],
        grid_size: int = 8
    ) -> Tuple[int, int, int, int]:
        x_min, y_min, x_max, y_max = bbox
        return (
            (x_min // grid_size) * grid_size,
            (y_min // grid_size) * grid_size,
            ((x_max + grid_size - 1) // grid_size) * grid_size,
            ((y_max + grid_size - 1) // grid_size) * grid_size,
        )

    # ---------- Main refinement ----------

    def refine_bbox(
        self,
        image: np.ndarray,
        bbox_normalized: Tuple[float, float, float, float],
        use_edge_detection: bool = True,
        use_grid_snap: bool = True,
        grid_size: int = 8,
    ) -> Tuple[float, float, float, float]:

        height, width = image.shape[:2]
        orig_x_min, orig_y_min, orig_x_max, orig_y_max = self.denormalize_bbox(
            bbox_normalized, width, height
        )
        x_min, y_min, x_max, y_max = orig_x_min, orig_y_min, orig_x_max, orig_y_max

        if (x_max - x_min) < 5 or (y_max - y_min) < 5:
            return bbox_normalized

        if use_edge_detection:
            edge = self.detect_edges_in_region(
                image, (x_min, y_min, x_max, y_max)
            )
            if edge and edge.confidence >= self.min_edge_confidence:
                new_x_min, new_y_min, new_x_max, new_y_max = (
                    edge.left,
                    edge.top,
                    edge.right,
                    edge.bottom,
                )
                old_area = max(1, (orig_x_max - orig_x_min) * (orig_y_max - orig_y_min))
                new_area = max(1, (new_x_max - new_x_min) * (new_y_max - new_y_min))
                area_ratio = new_area / float(old_area)
                # Avoid collapsing valid controls/text to tiny fragments.
                if area_ratio >= 0.20 or edge.confidence >= 0.35:
                    x_min, y_min, x_max, y_max = (
                        new_x_min,
                        new_y_min,
                        new_x_max,
                        new_y_max,
                    )

        if use_grid_snap:
            x_min, y_min, x_max, y_max = self.snap_to_grid(
                (x_min, y_min, x_max, y_max), grid_size
            )

        return self.normalize_bbox(
            (x_min, y_min, x_max, y_max), width, height
        )

    # ---------- Validation ----------

    def validate_bbox(self, bbox: Tuple[float, float, float, float]) -> bool:
        x_min, y_min, x_max, y_max = bbox
        if not all(0.0 <= v <= 1.0 for v in bbox):
            return False
        if x_min >= x_max or y_min >= y_max:
            return False
        area = (x_max - x_min) * (y_max - y_min)
        return area >= 0.00003


# =========================
# Folder-level Runner
# =========================

def run_bbox_refinement(
    image_dir: str,
    bbox_dir: str,
    output_dir: str,
    debug_visuals: bool = True,
):
    image_dir = Path(image_dir)
    bbox_dir = Path(bbox_dir)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    if debug_visuals:
        (output_dir / "debug").mkdir(exist_ok=True)

    refiner = BBoxRefiner()

    for bbox_file in bbox_dir.glob("*.json"):
        image_path = image_dir / f"{bbox_file.stem}.jpg"
        if not image_path.exists():
            continue

        image = cv2.imread(str(image_path))
        if image is None:
            continue
        h, w = image.shape[:2]

        with open(bbox_file, "r") as f:
            data = json.load(f)

        refined_boxes = []

        for item in data.get("bboxes", []):
            refined = refiner.refine_bbox(
                image=image,
                bbox_normalized=refiner.item_to_bbox(item),
            )

            if refiner.validate_bbox(refined):
                screen_bbox = tuple(item.get("screen_bbox", [0.0, 0.0, 1.0, 1.0]))
                dx, dy = refiner.bbox_to_center_pixels(refined, w, h)
                refined_boxes.append({
                    "dxdy": list(refiner.bbox_to_dxdy(refined, screen_bbox)),
                    "dx": dx,
                    "dy": dy,
                    "screen_bbox": list(screen_bbox),
                    "source": "ui_detector",
                    "confidence": item.get("confidence", 0.5),
                })

        out_path = output_dir / bbox_file.name
        with open(out_path, "w") as f:
            json.dump({"bboxes": refined_boxes}, f, indent=2)

        if debug_visuals:
            vis = image.copy()
            for r in refined_boxes:
                x1, y1, x2, y2 = refiner.item_to_bbox(r)
                cv2.rectangle(
                    vis,
                    (int(x1 * w), int(y1 * h)),
                    (int(x2 * w), int(y2 * h)),
                    (0, 255, 0),
                    2,
                )
            cv2.imwrite(
                str(output_dir / "debug" / image_path.name),
                vis,
            )

        print(f"[BBoxRefiner] Processed {bbox_file.name}")


# =========================
# CLI Entry
# =========================

if __name__ == "__main__":
    run_bbox_refinement(
        image_dir="data/preprocessed_frames",
        bbox_dir="data/coarse_bboxes",
        output_dir="data/refined_bboxes",
        debug_visuals=True,
    )
