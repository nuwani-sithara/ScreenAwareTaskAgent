# src/perception/vlm/prompt_templates.py
"""
Prompt templates for VLM-based UI detection and analysis.
"""

from typing import Optional

UI_DISCOVERY_PROMPT = """
You are an expert UI/UX analyst and visual interpreter.

Your task: Detect and identify ALL visible UI elements in the provided screenshot.

For each element, analyze and extract:
1. **Type**: button, input_field, text, label, icon, dropdown, checkbox, radio, menu, tab, modal, dialog, etc.
2. **Label/Text**: The visible text or descriptive label
3. **Description**: Purpose or role (e.g., "submit button", "search input", "close dialog")
4. **State**: If applicable (e.g., active, disabled, hover, focused)
5. **Bounding Box**: Approximate location as [x_min, y_min, x_max, y_max] (use 0-1 normalized coordinates or pixel coords)
6. **Confidence**: Your confidence level (0-1) in the detection

Return output as a JSON array with structure:
```json
{
  "elements": [
    {{
      "id": "element_1",
      "type": "button",
      "label": "Login",
      "description": "Primary action button for user authentication",
      "state": "active",
      "bbox": [0.35, 0.7, 0.65, 0.85],
      "confidence": 0.95
    }},
    {{
      "id": "element_2",
      "type": "input_field",
      "label": "Username",
      "description": "Text input for username entry",
      "state": "focused",
      "bbox": [0.1, 0.3, 0.9, 0.45],
      "confidence": 0.92
    }}
  ],
  "page_structure": {{
    "title": "Login Screen",
    "layout": "centered form",
    "background_color": "light",
    "density": "normal"
  }}
}
```

**Important Guidelines:**
- Identify ALL visible UI elements (don't skip any)
- Use normalized coordinates (0-1) if image dimensions are unknown
- Order elements top-to-bottom, left-to-right
- Include invisible but important elements (e.g., hidden menus, collapsed sections)
- If text is cut off or partially visible, still extract what you can see
- Rate your confidence based on clarity and distinctiveness

Return ONLY valid JSON. Do not include markdown or explanations.
"""

ELEMENT_REFINEMENT_PROMPT = """
Given a screenshot and a list of detected UI elements with approximate bounding boxes, 
refine and improve the bounding box accuracy.

For each element:
1. Verify the element exists and is correctly classified
2. Adjust bounding box to tightly fit the element
3. Resolve any overlaps or conflicts
4. Add missing visual features

Return corrected elements in the same JSON format.
"""

SEMANTIC_STATE_PROMPT = """
Given the detected UI elements from a screenshot, analyze the semantic state of the UI.

Extract:
1. **Page/Screen Type**: What kind of interface is this? (e.g., login form, game board, menu)
2. **Interactive State**: Which elements are enabled/disabled/focused?
3. **Meaningful Groups**: Logically group related elements (e.g., form field + label)
4. **User Intent**: What action might a user take next?

Return as JSON:
```json
{
  "screen_type": "game_board",
  "state": {{
    "active_elements": ["tile_1", "tile_2"],
    "disabled_elements": ["undo_button"],
    "focused_element": "tile_3"
  }},
  "groups": [
    {{
      "name": "board",
      "elements": ["tile_1", "tile_2", ...]
    }}
  ],
  "likely_actions": ["swipe up", "tap tile", "restart"]
}
```
"""

COMPARISON_PROMPT = """
Given two UI screenshots (current and reference), identify:
1. What elements are the same?
2. What elements are new?
3. What elements have changed position/appearance?
4. What elements are missing?

Return as JSON highlighting the differences.
"""


def get_ui_discovery_prompt(image_context: Optional[str] = None) -> str:
    """Get the main UI discovery prompt, with optional context."""
    if image_context:
        return f"{UI_DISCOVERY_PROMPT}\n\nContext about this image: {image_context}"
    return UI_DISCOVERY_PROMPT


def get_element_refinement_prompt(element_count: int) -> str:
    """Get refinement prompt with element count context."""
    return f"{ELEMENT_REFINEMENT_PROMPT}\n\nThere are {element_count} elements to refine."


def get_semantic_state_prompt() -> str:
    """Get semantic state analysis prompt."""
    return SEMANTIC_STATE_PROMPT


def get_comparison_prompt() -> str:
    """Get comparison prompt for detecting changes."""
    return COMPARISON_PROMPT
