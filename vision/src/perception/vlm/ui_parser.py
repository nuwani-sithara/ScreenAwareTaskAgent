# src/perception/vlm/ui_parser.py
"""
Parse and validate VLM output (JSON) into structured UI element representations.
"""

import json
import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict


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

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "description": self.description,
            "state": self.state,
            "bbox": list(self.bbox),
            "confidence": self.confidence
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UIElement":
        """Create from dictionary."""
        bbox = data.get("bbox", [0, 0, 1, 1])
        if isinstance(bbox, list):
            bbox = tuple(bbox)
        
        return cls(
            id=data.get("id", f"elem_{hash(str(data))}"),
            type=data.get("type", "unknown"),
            label=data.get("label", ""),
            description=data.get("description", ""),
            state=data.get("state", "normal"),
            bbox=bbox,
            confidence=float(data.get("confidence", 0.5)),
            raw_data=data
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

    def extract_json_from_response(self, response_text: str) -> Dict:
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
            return json.loads(json_str)
        
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
            
            # Check if already normalized (values between 0 and 1)
            if all(0 <= val <= 1 for val in [x_min, y_min, x_max, y_max]):
                return (float(x_min), float(y_min), float(x_max), float(y_max))
            
            # If pixel coordinates provided, normalize
            if image_width and image_height:
                return (
                    float(x_min) / image_width,
                    float(y_min) / image_height,
                    float(x_max) / image_width,
                    float(y_max) / image_height
                )
            
            # Assume normalized if can't determine
            return (float(x_min), float(y_min), float(x_max), float(y_max))
        
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
            if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
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
            
            # Parse elements
            elements_data = data.get("elements", [])
            elements = []
            
            for elem_data in elements_data:
                # Validate
                is_valid, error = self.validate_element(elem_data)
                if not is_valid:
                    print(f"Skipping invalid element: {error}")
                    continue
                
                # Normalize type
                elem_type = self.normalize_element_type(elem_data.get("type", "unknown"))
                
                # Normalize bbox
                bbox = self.normalize_bbox(
                    elem_data.get("bbox", [0, 0, 1, 1]),
                    image_width,
                    image_height
                )
                
                # Create element
                element = UIElement(
                    id=elem_data.get("id", f"elem_{len(elements)}"),
                    type=elem_type,
                    label=str(elem_data.get("label", "")),
                    description=str(elem_data.get("description", "")),
                    state=str(elem_data.get("state", "normal")),
                    bbox=bbox,
                    confidence=float(elem_data.get("confidence", 0.7)),
                    raw_data=elem_data
                )
                elements.append(element)
            
            # Parse page structure
            page_structure = data.get("page_structure", None)
            
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
