# src/perception/vlm/prompt_templates.py
"""
Prompt templates for VLM-based UI detection and analysis.
"""

from typing import Optional

UI_DISCOVERY_PROMPT = """
You are a strict UI parser for automation. Your job: return a complete list of
every visible UI element in the screenshot as a single JSON object and nothing
else. Follow the rules exactly.

Required rules (read carefully):
1) Return ONLY valid JSON with a single top-level object. No prose, no
   markdown, no commentary, no extra keys outside the schema shown below.
2) Output must include an "elements" array. Each element must contain the
   fields: "id", "type", "label", "description", "state", "bbox",
   "confidence".
3) Use bbox = [x_min, y_min, x_max, y_max] and PROVIDE ABSOLUTE PIXEL
   COORDINATES from the exact screenshot. Do NOT normalize to 0..1.
   Ensure x_min < x_max and y_min < y_max.
4) Labels and descriptions must never be empty. If no visible text exists,
   generate a concise functional label (examples: "menu icon", "submit button",
   "username input"). Descriptions should be one concrete sentence about what
   the element shows or what it does (short, not generic).
5) Use the allowed `type` values only: button, input_field, text, label, icon,
   dropdown, checkbox, radio, menu, tab, modal, dialog, link, card, list_item,
   image, unknown. Prefer a specific type; use "unknown" only as a last resort.
6) `state` must be one of: enabled, disabled, focused, checked, unchecked,
   normal. Use `normal` when unsure.
7) `confidence` is a float between 0.0 and 1.0 representing your certainty.
8) Keep bounding boxes tight: each bbox should tightly enclose the visible
   control (do not include large whitespace or unrelated nearby elements).
9) If an element is partially off-screen, clip the bbox to the visible area.
10) Do NOT invent interactions not visible in the screenshot (no hover hints,
    no tooltips unless visible).

Output schema (exact):
{
  "elements": [
    {
      "id": "elem_0",
      "type": "button",
      "label": "Save",
      "description": "Primary action saving the form.",
      "state": "enabled",
   "bbox": [680, 720, 1230, 820],
      "confidence": 0.95
    }
  ]
}

Small concrete example (use this style exactly):
{
  "elements": [
    {"id":"username_input","type":"input_field","label":"Username","description":"Text input where the user types their username.","state":"normal","bbox":[520,410,1120,470],"confidence":0.96},
    {"id":"password_input","type":"input_field","label":"Password","description":"Text input for the user password (masked).","state":"normal","bbox":[520,495,1120,555],"confidence":0.95},
    {"id":"login_button","type":"button","label":"LOGIN","description":"Primary action to submit credentials and sign in.","state":"enabled","bbox":[540,610,1110,690],"confidence":0.98}
  ]
}

If the screenshot contains many elements, return them all. Keep labels short
(2-6 words) and descriptions concise (one sentence). Do not return any other
top-level keys or additional metadata. Follow the schema and normalization
rules; incorrect formats will be rejected.
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
