# src/perception/vlm/prompt_templates.py
"""
Prompt templates for VLM-based UI detection and analysis.
"""

from typing import Optional

UI_DISCOVERY_PROMPT = """
You are an expert visual UI parser for agent automation.

Task:
Detect ALL VISIBLE on-screen UI elements in the screenshot. Prioritize recall:
include small icons, toolbar items, tabs, toggles, chips, links, badges, table rows,
cards, list items, text labels, and form controls.

Rules:
1. Return ONLY valid JSON (no markdown, no prose).
2. Detect visible elements only. Do not hallucinate hidden/off-screen elements.
3. Bounding boxes must be tight and axis-aligned.
4. Use [x_min, y_min, x_max, y_max] with x_min < x_max and y_min < y_max.
5. Coordinates may be normalized (0-1) or pixels. Be internally consistent.
6. Read and include visible text exactly when possible.
7. Keep confidence realistic (0.0-1.0).
8. If unsure of class, use type "unknown" but still include the element.

For each element include:
- id
- type (button, input_field, text, label, icon, dropdown, checkbox, radio, menu, tab, modal, dialog, link, card, list_item, image, unknown)
- label
- description
- state
- bbox
- confidence

Output schema:
{
  "elements": [
    {
      "id": "element_1",
      "type": "button",
      "label": "Login",
      "description": "Primary authentication action",
      "state": "enabled",
      "bbox": [0.35, 0.70, 0.65, 0.85],
      "confidence": 0.95
    }
  ],
  "page_structure": {
    "title": "short title",
    "layout": "brief layout description",
    "density": "sparse|normal|dense"
  }
}
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


def get_ui_discovery_prompt(
    image_context: Optional[str] = None,
    screen_region: Optional[str] = None,
) -> str:
    """Get the main UI discovery prompt, with optional context."""
    extra_context = []
    if image_context:
        extra_context.append(f"Context: {image_context}")
    if screen_region:
        extra_context.append(f"Analyze this region only: {screen_region}")
    if extra_context:
        return f"{UI_DISCOVERY_PROMPT}\n\n" + "\n".join(extra_context)
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
