# src/interpretation/semantic_state_builder.py
"""
Build semantic game/UI state from VLM-detected UI elements.
Works with generalized UI elements instead of specific game elements.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
try:
    # Works when running scripts directly from src/
    from perception import UIElement
except ImportError:
    # Works when imported as part of the src package
    from ..perception import UIElement


@dataclass
class InteractiveElement:
    """Represents an interactive UI element with semantic meaning."""
    id: str
    type: str  # button, input, text, icon, etc.
    label: str
    bbox: Tuple[float, float, float, float]
    state: str
    role: Optional[str] = None  # "action", "display", "input", etc.
    value: Optional[str] = None
    confidence: float = 0.5


class SemanticStateBuilder:
    """
    Build semantic state from VLM-detected elements.
    
    This replaces game-specific interpretation with general-purpose UI reasoning.
    """

    def __init__(self):
        """Initialize builder."""
        self.element_roles = {
            "button": "action",
            "menu_item": "action",
            "link": "action",
            "input_field": "input",
            "text_field": "input",
            "textarea": "input",
            "checkbox": "input",
            "radio": "input",
            "dropdown": "input",
            "slider": "input",
            "text": "display",
            "label": "display",
            "icon": "display",
            "image": "display",
            "modal": "container",
            "dialog": "container",
            "menu": "container"
        }

    def classify_element(self, element: UIElement) -> InteractiveElement:
        """
        Classify UI element and assign semantic role.
        
        Args:
            element: Detected UI element
        
        Returns:
            InteractiveElement with semantic classification
        """
        role = self.element_roles.get(element.type, "unknown")
        
        # Infer state more precisely
        state = element.state or "normal"
        if "disabled" in element.description.lower():
            state = "disabled"
        elif "focused" in element.description.lower():
            state = "focused"
        elif "active" in element.description.lower():
            state = "active"
        
        return InteractiveElement(
            id=element.id,
            type=element.type,
            label=element.label,
            bbox=element.bbox,
            state=state,
            role=role,
            confidence=element.confidence
        )

    def group_related_elements(self, elements: List[InteractiveElement]) -> Dict[str, List[InteractiveElement]]:
        """
        Group logically related elements (e.g., label + input field).
        
        Args:
            elements: List of interactive elements
        
        Returns:
            Dict mapping group names to lists of elements
        """
        groups = {
            "inputs": [],
            "actions": [],
            "displays": [],
            "containers": [],
            "other": []
        }
        
        for elem in elements:
            if elem.role == "input":
                groups["inputs"].append(elem)
            elif elem.role == "action":
                groups["actions"].append(elem)
            elif elem.role == "display":
                groups["displays"].append(elem)
            elif elem.role == "container":
                groups["containers"].append(elem)
            else:
                groups["other"].append(elem)
        
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}

    def find_input_label_pairs(self, elements: List[InteractiveElement]) -> List[Tuple[InteractiveElement, Optional[InteractiveElement]]]:
        """
        Find input fields and their associated labels.
        
        Heuristic: labels are usually above or to the left of input fields.
        
        Args:
            elements: List of elements
        
        Returns:
            List of (input, label) tuples
        """
        pairs = []
        inputs = [e for e in elements if e.role == "input"]
        labels = [e for e in elements if e.type == "label"]
        
        for inp in inputs:
            x_min, y_min, x_max, y_max = inp.bbox
            
            # Find closest label above or to the left
            closest_label = None
            min_distance = float('inf')
            
            for label in labels:
                lx_min, ly_min, lx_max, ly_max = label.bbox
                
                # Check if label is above or to the left
                if ly_max <= y_min or lx_max <= x_min:
                    # Calculate distance
                    dx = max(0, x_min - lx_max, lx_min - x_max)
                    dy = max(0, y_min - ly_max, ly_min - y_max)
                    distance = dx + dy
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_label = label
            
            pairs.append((inp, closest_label))
        
        return pairs

    def build_semantic_state(self, elements: List[UIElement]) -> Dict[str, Any]:
        """
        Build semantic state from detected elements.
        
        Args:
            elements: List of detected UI elements from VLM
        
        Returns:
            Dict representing semantic UI state
        """
        # Classify elements
        classified = [self.classify_element(elem) for elem in elements]
        
        # Sort by position (top-left to bottom-right)
        classified.sort(key=lambda e: (e.bbox[1], e.bbox[0]))
        
        # Group elements
        groups = self.group_related_elements(classified)
        
        # Find input-label pairs
        input_pairs = self.find_input_label_pairs(classified)
        
        # Build state
        state = {
            "elements": [asdict(elem) for elem in classified],
            "groups": {
                name: [asdict(elem) for elem in group]
                for name, group in groups.items()
            },
            "input_pairs": [
                {
                    "input": asdict(inp),
                    "label": asdict(label) if label else None
                }
                for inp, label in input_pairs
            ],
            "interactive_elements": [
                asdict(elem) for elem in classified
                if elem.role in ["action", "input"]
            ],
            "summary": {
                "total_elements": len(classified),
                "actionable_elements": len([e for e in classified if e.role == "action"]),
                "input_elements": len([e for e in classified if e.role == "input"]),
                "display_elements": len([e for e in classified if e.role == "display"])
            }
        }
        
        return state

    def find_clickable_elements(self, state: Dict[str, Any],
                               min_confidence: float = 0.5) -> List[InteractiveElement]:
        """Find all clickable/actionable elements in state."""
        elements_data = state.get("groups", {}).get("actions", [])
        
        clickable = []
        for elem_data in elements_data:
            if elem_data.get("confidence", 0.5) >= min_confidence:
                clickable.append(InteractiveElement(**elem_data))
        
        return clickable

    def find_input_elements(self, state: Dict[str, Any],
                           min_confidence: float = 0.5) -> List[InteractiveElement]:
        """Find all input elements in state."""
        elements_data = state.get("groups", {}).get("inputs", [])
        
        inputs = []
        for elem_data in elements_data:
            if elem_data.get("confidence", 0.5) >= min_confidence:
                inputs.append(InteractiveElement(**elem_data))
        
        return inputs

    def get_element_by_label(self, state: Dict[str, Any],
                            label: str) -> Optional[InteractiveElement]:
        """Find element by label (approximate substring match)."""
        for elem_data in state.get("elements", []):
            if label.lower() in elem_data.get("label", "").lower():
                return InteractiveElement(**elem_data)
        
        return None

    def get_element_at_position(self, state: Dict[str, Any],
                               x: float, y: float) -> Optional[InteractiveElement]:
        """
        Find element at approximate screen position.
        
        Args:
            state: Semantic state
            x, y: Normalized coordinates (0-1)
        
        Returns:
            Element at that position or None
        """
        for elem_data in state.get("elements", []):
            bbox = elem_data.get("bbox", [0, 0, 1, 1])
            x_min, y_min, x_max, y_max = bbox
            
            if x_min <= x <= x_max and y_min <= y <= y_max:
                return InteractiveElement(**elem_data)
        
        return None

    def compare_states(self, state1: Dict[str, Any],
                      state2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two semantic states and detect changes.
        
        Args:
            state1: First state
            state2: Second state
        
        Returns:
            Dict describing changes
        """
        elements1 = {e["id"]: e for e in state1.get("elements", [])}
        elements2 = {e["id"]: e for e in state2.get("elements", [])}
        
        added = set(elements2.keys()) - set(elements1.keys())
        removed = set(elements1.keys()) - set(elements2.keys())
        modified = []
        
        for elem_id in set(elements1.keys()) & set(elements2.keys()):
            if elements1[elem_id] != elements2[elem_id]:
                modified.append({
                    "id": elem_id,
                    "before": elements1[elem_id],
                    "after": elements2[elem_id]
                })
        
        return {
            "added": list(added),
            "removed": list(removed),
            "modified": modified,
            "summary": {
                "changes": len(added) + len(removed) + len(modified)
            }
        }
