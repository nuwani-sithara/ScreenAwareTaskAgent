# src/perception/vlm/ui_parser.py
"""
Parse and validate VLM output (JSON) into structured UI element representations.
"""

import json
import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass


@dataclass
class UIElement:
    """Represents a detected UI element."""
    id: str
    type: str
    label: str
    description: str
    state: str
    bbox: Tuple[float, float, float, float]  # [x_min, y_min, x_max, y_max]
    confidence: float
    raw_data: Optional[Dict] = None

    @staticmethod
    def _dxdy_to_bbox(
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

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        out: Dict[str, Any] = dict(self.raw_data) if isinstance(self.raw_data, dict) else {}
        out.update({
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "description": self.description,
            "state": self.state,
            "confidence": self.confidence
        })
        if "dx" in out:
            try:
                out["dx"] = int(round(float(out["dx"])))
            except Exception:
                pass
        if "dy" in out:
            try:
                out["dy"] = int(round(float(out["dy"])))
            except Exception:
                pass
        out.pop("bbox", None)
        out.pop("dxdy", None)
        out.pop("screen_bbox", None)
        return out

    @classmethod
    def from_dict(cls, data: Dict) -> "UIElement":
        """Create from dictionary."""
        bbox_raw = data.get("bbox")
        if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) == 4:
            bbox = tuple(float(v) for v in bbox_raw)
        else:
            dxdy = data.get("dxdy")
            screen_bbox = data.get("screen_bbox", [0, 0, 1, 1])
            if (
                isinstance(dxdy, (list, tuple))
                and len(dxdy) == 4
                and isinstance(screen_bbox, (list, tuple))
                and len(screen_bbox) == 4
            ):
                bbox = cls._dxdy_to_bbox(
                    tuple(float(v) for v in dxdy),
                    tuple(float(v) for v in screen_bbox),
                )
            else:
                bbox = (0.0, 0.0, 1.0, 1.0)

        return cls(
            id=data.get("id", f"elem_{hash(str(data))}"),
            type=data.get("type", "unknown"),
            label=data.get("label", ""),
            description=data.get("description", ""),
            state=data.get("state", "normal"),
            bbox=bbox,
            confidence=float(data.get("confidence", 0.5)),
            raw_data=dict(data)
        )


@dataclass
class UIAnalysisResult:
    """Result of VLM UI analysis."""
    elements: List[UIElement]
    page_structure: Optional[Dict] = None
    raw_response: Optional[str] = None
    parse_successful: bool = True
    parse_error: Optional[str] = None


class UIParser:
    """Parse and validate VLM responses."""

    def __init__(self):
        self.element_type_aliases = {
            "btn": "button",
            "input": "input_field",
            "txt": "text",
            "lbl": "label",
            "img": "icon",
            "icn": "icon",
            "dropdown": "dropdown",
            "select": "dropdown",
            "chk": "checkbox",
            "radio_btn": "radio",
            "menu_item": "menu",
            "tab_item": "tab",
        }

    @staticmethod
    def _sanitize_json_string(s: str) -> str:
        if not s:
            return s
        s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
        s = re.sub(r",\s*}\s*", "}", s)
        s = re.sub(r",\s*\]\s*", "]", s)
        return s

    @staticmethod
    def _coerce_json_text(text: str) -> str:
        s = text.replace("```json", "").replace("```", "")
        s = re.sub(r"//.*?$|/\*.*?\*/", "", s, flags=re.DOTALL | re.MULTILINE)
        s = s.replace("\u2018", "'").replace("\u2019", "'")
        s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', s)
        s = re.sub(r'([\{,\s])([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
        s = re.sub(r",\s*([}\]])", r"\1", s)
        s = re.sub(r"\bTrue\b", "true", s)
        s = re.sub(r"\bFalse\b", "false", s)
        s = re.sub(r"\bNone\b", "null", s)
        return s

    @staticmethod
    def _extract_partial_elements(response_text: str) -> List[Dict[str, Any]]:
        """
        Recover complete element objects from a truncated response.

        Gemini sometimes stops mid-array. When that happens, we can still keep any
        fully closed element objects that appeared before the truncation point.
        """
        key_match = re.search(r'"elements"\s*:\s*\[', response_text)
        if not key_match:
            return []

        idx = key_match.end()
        elements: List[Dict[str, Any]] = []
        in_str = False
        esc = False
        brace_depth = 0
        obj_start: Optional[int] = None

        while idx < len(response_text):
            ch = response_text[idx]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    if brace_depth == 0:
                        obj_start = idx
                    brace_depth += 1
                elif ch == "}":
                    if brace_depth > 0:
                        brace_depth -= 1
                        if brace_depth == 0 and obj_start is not None:
                            candidate = response_text[obj_start : idx + 1].strip()
                            parsed: Any = None
                            for variant in (
                                candidate,
                                UIParser._sanitize_json_string(candidate),
                                UIParser._coerce_json_text(candidate),
                            ):
                                try:
                                    parsed = json.loads(variant)
                                    break
                                except json.JSONDecodeError:
                                    continue
                            if isinstance(parsed, dict):
                                elements.append(parsed)
                            obj_start = None
                elif ch == "]" and brace_depth == 0:
                    break
            idx += 1

        return elements

    def extract_json_from_response(self, response_text: str) -> Any:
        """
        Extract JSON from VLM response text.
        Handles cases where response contains markdown code blocks or extra text.
        """
        # Remove markdown code blocks
        response_text = re.sub(r'```json\n?', '', response_text)
        response_text = re.sub(r'```\n?', '', response_text)

        # Try to find JSON object
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            for variant in (
                json_str,
                self._sanitize_json_string(json_str),
                self._coerce_json_text(json_str),
            ):
                try:
                    return json.loads(variant)
                except json.JSONDecodeError:
                    continue

        # Try JSON array root
        json_array_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_array_match:
            json_array = json_array_match.group(0)
            for variant in (
                json_array,
                self._sanitize_json_string(json_array),
                self._coerce_json_text(json_array),
            ):
                try:
                    return json.loads(variant)
                except json.JSONDecodeError:
                    continue

        partial_elements = self._extract_partial_elements(response_text)
        if partial_elements:
            return {"elements": partial_elements}

        # Fallback: try direct JSON parse
        return json.loads(response_text)

    def normalize_bbox(self, bbox: Any, image_width: Optional[int] = None,
                       image_height: Optional[int] = None) -> Tuple[float, float, float, float]:
        """
        Normalize bounding box to (0-1) range.
        If bbox is already normalized, returns as-is.
        """
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x_min, y_min, x_max, y_max = bbox
            try:
                x_min, y_min, x_max, y_max = (
                    float(x_min), float(y_min), float(x_max), float(y_max)
                )
            except (TypeError, ValueError):
                return (0.0, 0.0, 1.0, 1.0)

            # Normalize pixel coordinates if image dimensions are available and values look like pixels.
            if image_width and image_height and max(x_min, y_min, x_max, y_max) > 1.0:
                x_min /= float(image_width)
                x_max /= float(image_width)
                y_min /= float(image_height)
                y_max /= float(image_height)

            # Enforce ordering and clamp to [0, 1].
            x_low, x_high = sorted((x_min, x_max))
            y_low, y_high = sorted((y_min, y_max))
            x_low = max(0.0, min(1.0, x_low))
            y_low = max(0.0, min(1.0, y_low))
            x_high = max(0.0, min(1.0, x_high))
            y_high = max(0.0, min(1.0, y_high))

            return (x_low, y_low, x_high, y_high)
        
        # Invalid bbox
        return (0.0, 0.0, 1.0, 1.0)

    def normalize_element_type(self, element_type: str) -> str:
        """Normalize element type using aliases."""
        element_type = element_type.strip().lower()
        return self.element_type_aliases.get(element_type, element_type)

    def validate_element(self, elem_data: Dict) -> Tuple[bool, Optional[str]]:
        """Validate element data. Returns (is_valid, error_message)."""
        if not isinstance(elem_data, dict):
            return False, "Element is not a dictionary"
        
        # Check required fields
        required = ["bbox"]
        for field in required:
            if field not in elem_data:
                return False, f"Missing required field: {field}"
        
        # Validate bbox
        bbox = elem_data.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return False, "Invalid bbox format"
        
        # Confidence should be 0-1 if present
        if "confidence" in elem_data:
            conf = elem_data.get("confidence")
            try:
                conf_val = float(conf)
            except (TypeError, ValueError):
                return False, f"Invalid confidence: {conf}"
            if not (0 <= conf_val <= 1):
                return False, f"Invalid confidence: {conf}"
        
        return True, None

    def parse_vlm_response(self, response_text: str, 
                          image_width: Optional[int] = None,
                          image_height: Optional[int] = None) -> UIAnalysisResult:
        """
        Parse VLM response into structured UIAnalysisResult.
        
        Args:
            response_text: Raw response from VLM
            image_width: Image width for bbox normalization
            image_height: Image height for bbox normalization
        
        Returns:
            UIAnalysisResult with parsed elements
        """
        try:
            # Extract JSON
            data = self.extract_json_from_response(response_text)

            # Parse elements from either {"elements": [...]} or direct [...] output
            if isinstance(data, dict):
                elements_data = data.get("elements", [])
                page_structure = data.get("page_structure", None)
            elif isinstance(data, list):
                elements_data = data
                page_structure = None
            else:
                raise ValueError("Unexpected JSON root type")
            elements = []

            # Heuristic: some VLMs return absolute pixel coords but relative to
            # an internal/resized canvas (e.g. 1024px wide) instead of the
            # original image. If that's the case we detect a global bbox max
            # smaller than the real image size and rescale the coordinates
            # before normalization so boxes map correctly to the original.
            scale_x = 1.0
            scale_y = 1.0
            try:
                if image_width and image_height and isinstance(elements_data, list) and elements_data:
                    max_x = 0.0
                    max_y = 0.0
                    for e in elements_data:
                        b = e.get("bbox")
                        if isinstance(b, (list, tuple)) and len(b) == 4:
                            try:
                                x1, y1, x2, y2 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                                max_x = max(max_x, x1, x2)
                                max_y = max(max_y, y1, y2)
                            except Exception:
                                continue
                    # If the largest reported coordinate is noticeably smaller
                    # than the actual image dimension, assume coords were given
                    # on a resized canvas and compute a scale factor.
                    if max_x > 1.0 and max_y > 1.0:
                        if max_x < float(image_width) * 0.95 and (float(image_width) / max_x) > 1.2:
                            scale_x = float(image_width) / max_x
                        if max_y < float(image_height) * 0.95 and (float(image_height) / max_y) > 1.2:
                            scale_y = float(image_height) / max_y
                        # If scales are wildly different, fall back to uniform scale
                        if scale_x > 1.0 and scale_y > 1.0:
                            if abs(scale_x - scale_y) / max(scale_x, scale_y) < 0.35:
                                scale = (scale_x + scale_y) / 2.0
                                scale_x = scale_y = scale
            except Exception:
                scale_x = scale_y = 1.0

            for elem_data in elements_data:
                # Validate
                is_valid, error = self.validate_element(elem_data)
                if not is_valid:
                    print(f"Skipping invalid element: {error}")
                    continue
                
                # Normalize type
                elem_type = self.normalize_element_type(elem_data.get("type", "unknown"))
                
                # Normalize bbox (apply inferred scale if VLM returned coords on
                # a resized canvas)
                raw_bbox = elem_data.get("bbox", [0, 0, 1, 1])
                try:
                    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4 and (scale_x != 1.0 or scale_y != 1.0):
                        # Scale x coords by scale_x and y coords by scale_y
                        rb = [float(raw_bbox[0]) * scale_x, float(raw_bbox[1]) * scale_y, float(raw_bbox[2]) * scale_x, float(raw_bbox[3]) * scale_y]
                    else:
                        rb = raw_bbox
                except Exception:
                    rb = raw_bbox

                bbox = self.normalize_bbox(
                    rb,
                    image_width,
                    image_height
                )
                
                # Create element
                conf = elem_data.get("confidence", 0.7)
                try:
                    conf = float(conf)
                except (TypeError, ValueError):
                    conf = 0.7
                conf = max(0.0, min(1.0, conf))

                element = UIElement(
                    id=elem_data.get("id", f"elem_{len(elements)}"),
                    type=elem_type,
                    label=str(elem_data.get("label", "")),
                    description=str(elem_data.get("description", "")),
                    state=str(elem_data.get("state", "normal")),
                    bbox=bbox,
                    confidence=conf,
                    raw_data=elem_data
                )
                elements.append(element)

            return UIAnalysisResult(
                elements=elements,
                page_structure=page_structure,
                raw_response=response_text,
                parse_successful=True
            )
        
        except json.JSONDecodeError as e:
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error=f"JSON decode error: {str(e)}",
                raw_response=response_text
            )
        except Exception as e:
            return UIAnalysisResult(
                elements=[],
                parse_successful=False,
                parse_error=f"Parse error: {str(e)}",
                raw_response=response_text
            )

    def to_dict(self, result: UIAnalysisResult) -> Dict:
        """Convert result to dictionary."""
        return {
            "elements": [elem.to_dict() for elem in result.elements],
            "page_structure": result.page_structure,
            "parse_successful": result.parse_successful,
            "parse_error": result.parse_error,
            "element_count": len(result.elements)
        }
