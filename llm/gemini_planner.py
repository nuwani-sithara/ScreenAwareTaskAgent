"""
Gemini-based planning functions for the V2 agentic AI loop.

Provides four core LLM planning capabilities:
  1. plan_todo_list      – Analyze screen + task → ordered step list
  2. plan_step_hid       – Current screen + step → HID command sequence
  3. evaluate_step_result– Post-execution screen + step → success/retry/needs_input
  4. generate_final_report – Final screen + history → user-facing summary
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from llm.gemini_client import GeminiClient

# Single decoder instance for raw_decode (thread-safe for read operations)
_JSON_DECODER = json.JSONDecoder()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared system context injected at the top of every prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are ScreenPilot, an expert AI agent that controls computers by \
analyzing screen contents and sending precise HID (Human Interface Device) commands.

Your capabilities:
- Analyze UI elements (buttons, text fields, dropdowns, menus, icons)
- Generate exact HID commands for mouse and keyboard control
- Self-validate step completion by comparing screen states
- Detect when user input is required (passwords, personal data, OTP codes)

HID Command Reference:
  {"cmd": "mouse_move",  "dx": N, "dy": N}                   — move cursor to absolute screen position (dx/dy = pixels from screen top-left)
  {"cmd": "mouse_click", "button": "left"|"right"|"middle"}  — click at current cursor position
  {"cmd": "key_press",   "key": "enter"|"tab"|"escape"|"backspace"|"space"}  — single key
  {"cmd": "key_combo",   "key": "c", "modifiers": ["ctrl"]}  — modifier combos (e.g. Ctrl+C)
  {"cmd": "type_text",   "text": "..."}                      — type a string of characters
  {"cmd": "mouse_scroll","deltaY": N}                        — scroll (positive=down, negative=up)

When clicking an element: ALWAYS send mouse_move first, then mouse_click.
Use the exact dx/dy pixel coordinates shown in the screen elements list.

IMPORTANT: Always respond with ONLY valid JSON — no markdown fences, no prose."""


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _find_all_json(text: str) -> List[Any]:
    """
    Scan *text* and return all valid JSON values (objects or arrays) found,
    in the order they appear.  Uses raw_decode so trailing content after the
    first closing brace/bracket is handled correctly.

    Thinking models (gemini-flash, gemini-pro-exp) emit a thinking block first
    and the real answer second, so callers can take ``results[-1]``.
    """
    results: List[Any] = []
    i = 0
    while i < len(text):
        # Jump to the next potential JSON opener
        nxt = next((j for j in range(i, len(text)) if text[j] in ('{', '[')), None)
        if nxt is None:
            break
        try:
            val, end_pos = _JSON_DECODER.raw_decode(text, nxt)
            results.append(val)
            i = end_pos
        except json.JSONDecodeError:
            i = nxt + 1
    return results


def _extract_json(text: str) -> Any:
    """
    Robustly extract a JSON value from an LLM response.

    Strategy (in order):
    1. Direct full-text parse.
    2. Strip markdown code fence and parse inner text.
    3. Find ALL valid JSON values in the text and return the LAST one.
       (Thinking models output a thinking block first then the real answer.)
    """
    text = text.strip().lstrip("\ufeff").strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find all valid JSON objects/arrays; return the last one.
    #    Thinking models emit {<thinking>}\n{<actual response>} — the last
    #    complete JSON is the real answer.
    candidates = _find_all_json(text)
    if candidates:
        return candidates[-1]

    raise ValueError(f"No valid JSON found in LLM response: {text[:300]!r}")


# ---------------------------------------------------------------------------
# Screen data → exact element list (preserves original coordinates)
# ---------------------------------------------------------------------------

def _extract_elements(screen_data: dict) -> List[dict]:
    """
    Extract detected UI elements with exact pixel coordinates from raw vision data.
    Returns a list of dicts: {type, label, dx, dy}.
    Coordinates are taken verbatim from what the vision service reported.
    """
    raw_elements: List[dict] = []
    if "elements" in screen_data:
        raw_elements = screen_data.get("elements", [])
    elif "vision_data" in screen_data:
        raw_elements = screen_data["vision_data"].get("elements", [])
    elif "session_data" in screen_data:
        screens = screen_data["session_data"].get("screens", [])
        if screens:
            raw_elements = screens[-1].get("elements", [])
    elif "screens" in screen_data:
        screens = screen_data.get("screens", [])
        if screens:
            raw_elements = screens[-1].get("elements", [])

    result: List[dict] = []
    for i, el in enumerate(raw_elements):
        bbox = el.get("bbox") or {}
        x = (
            el.get("dx") or el.get("x") or el.get("cx")
            or bbox.get("x") or bbox.get("cx")
        )
        y = (
            el.get("dy") or el.get("y") or el.get("cy")
            or bbox.get("y") or bbox.get("cy")
        )
        if x is None or y is None:
            continue
        result.append({
            "id": i + 1,
            "type": el.get("type", "element"),
            "label": el.get("label") or el.get("text") or "",
            "description": el.get("description") or "",
            "dx": int(x),
            "dy": int(y),
        })
    return result


def _snap_to_detected_elements(
    hid_commands: List[dict],
    detected: List[dict],
    threshold: int = 120,
) -> List[dict]:
    """
    For every mouse_move in hid_commands, replace its dx/dy with the
    exact coordinates of the nearest detected element (if within *threshold*
    pixels).  This corrects for the LLM slightly rounding or hallucinating
    coordinates it read from the prompt text.
    """
    if not detected:
        return hid_commands

    snapped: List[dict] = []
    for cmd in hid_commands:
        if cmd.get("cmd") == "mouse_move" and "dx" in cmd and "dy" in cmd:
            tx, ty = int(cmd["dx"]), int(cmd["dy"])
            best: Optional[dict] = None
            best_dist = float("inf")
            for el in detected:
                dist = ((el["dx"] - tx) ** 2 + (el["dy"] - ty) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best = el

            if best is not None and best_dist <= threshold:
                logger.debug(
                    "Snap mouse_move (%d,%d) → (%d,%d) [%s '%s', dist=%.1fpx]",
                    tx, ty, best["dx"], best["dy"],
                    best.get("type"), best.get("label"), best_dist,
                )
                snapped.append({**cmd, "dx": best["dx"], "dy": best["dy"]})
            else:
                logger.debug(
                    "No snap for mouse_move (%d,%d) — nearest element %.1fpx away",
                    tx, ty, best_dist if best else -1,
                )
                snapped.append(cmd)
        else:
            snapped.append(cmd)
    return snapped


# ---------------------------------------------------------------------------
# Screen data → readable text
# ---------------------------------------------------------------------------

def _screen_to_text(screen_data: dict) -> str:
    """
    Convert raw vision-service output to a concise text summary.

    Handles both capture formats:
      - Single-shot:  {"elements": [...], "visual_summary": "..."}
      - Session stop: {"session_data": {"screens": [{"elements": [...]}]}}
    """
    elements: List[dict] = []
    description: str = ""

    if "elements" in screen_data:
        elements = screen_data.get("elements", [])
        description = (
            screen_data.get("visual_summary", "")
            or screen_data.get("scene_description", "")
        )
    elif "vision_data" in screen_data:
        # Single-shot /vision/capture response: elements are nested under 'vision_data'
        vd = screen_data["vision_data"]
        elements = vd.get("elements", [])
        description = vd.get("visual_summary", "") or vd.get("scene_description", "")
    elif "session_data" in screen_data:
        screens = screen_data["session_data"].get("screens", [])
        if screens:
            latest = screens[-1]
            elements = latest.get("elements", [])
            description = latest.get("visual_summary", "")
    elif "screens" in screen_data:
        screens = screen_data.get("screens", [])
        if screens:
            elements = screens[-1].get("elements", [])

    lines: List[str] = []
    if description:
        lines.append(f"Scene description: {description}")

    if elements:
        lines.append(f"UI Elements ({len(elements)} detected):")
        for el in elements[:50]:
            el_type = el.get("type", "element")
            label = el.get("label") or el.get("text") or ""
            desc  = el.get("description") or ""
            bbox  = el.get("bbox") or {}

            # Vision service uses 'dx'/'dy' as pixel-space centre coordinates.
            # Fall back to common alternatives for forward-compatibility.
            x = (
                el.get("dx") or el.get("x") or el.get("cx")
                or bbox.get("x") or bbox.get("cx")
            )
            y = (
                el.get("dy") or el.get("y") or el.get("cy")
                or bbox.get("y") or bbox.get("cy")
            )
            w = el.get("w") or el.get("width")  or bbox.get("width")
            h = el.get("h") or el.get("height") or bbox.get("height")

            pos  = f" @ ({int(x)}, {int(y)})" if x is not None and y is not None else ""
            size = f" [{int(w)}×{int(h)}]" if w and h else ""
            lbl  = f" '{label}'" if label else ""
            dsc  = f" — {desc}" if desc and desc != label else ""
            lines.append(f"  - [{el_type}]{lbl}{pos}{size}{dsc}")
    elif not description:
        lines.append("No UI elements detected. Screen may be loading or empty.")

    return "\n".join(lines) if lines else "Screen data unavailable."


# ---------------------------------------------------------------------------
# 1.  plan_todo_list
# ---------------------------------------------------------------------------

def plan_todo_list(
    screen_data: dict,
    user_task: str,
    model: str = "models/gemini-flash-latest",
) -> dict:
    """
    Analyze the current screen and produce an ordered todo list.

    Returns::

        {
          "steps": [
            {
              "id": 1,
              "action": "Click the Login button",
              "target": "Button labeled 'Login' at (800, 400)",
              "expected_result": "Login dialog appears",
              "needs_user_data": false,
              "user_data_field": null
            },
            ...
          ],
          "notes": "Brief analysis of screen state and approach",
          "estimated_complexity": "simple|moderate|complex"
        }
    """
    screen_text = _screen_to_text(screen_data)

    prompt = f"""{SYSTEM_PROMPT}

TASK: Analyze the screen and create an ordered todo list to accomplish the user's goal.

=== CURRENT SCREEN ===
{screen_text}

=== USER'S TASK ===
{user_task}

=== RULES ===
- A STEP represents ALL interactions that can be completed on the CURRENT visible
  screen before any navigation or UI change occurs.
- Group ALL sub-actions on the same screen (clicks, keypresses, text entry) into
  a SINGLE step. Do NOT split them into separate steps.
- Create a NEW step only when you expect a visible UI change after the previous
  step completes (e.g. a new page loads, a dialog opens, a form navigates away).
- EXAMPLE — Login form: clicking username, typing credentials, clicking password,
  typing, then clicking LOGIN are all ONE step, because they all happen on the
  same screen. The step AFTER that handles whatever screen appears post-login.
- In the "action" field, describe ALL sub-actions to perform in order
  (e.g. "Click username field, type 'admin', click password field, type password,
  click the LOGIN button").
- Set "needs_user_data": true ONLY when the step requires information only the
  user can supply (password, email, OTP, personal name, etc.).
- "user_data_field" is a short snake_case field name (e.g. "password") when
  needs_user_data is true, otherwise null.

Respond with ONLY this JSON object (no markdown):
{{
  "steps": [
    {{
      "id": 1,
      "action": "Click the username field, type 'admin', click the password field, type the password, click the LOGIN button",
      "target": "Login form elements visible on current screen",
      "expected_result": "Logged in — dashboard or home page loads",
      "needs_user_data": false,
      "user_data_field": null
    }}
  ],
  "notes": "Brief description of the screen state and what needs to happen",
  "estimated_complexity": "simple"
}}"""

    client = GeminiClient()
    try:
        raw = client.generate(
            prompt, model=model, max_tokens=4000, temperature=0.2,
            response_mime_type="application/json",
        )
        logger.debug("plan_todo_list raw response: %s", raw[:600])
        result = _extract_json(raw)
        steps = result.get("steps")
        # Handle case where LLM returns steps as a single dict instead of a list
        if isinstance(steps, dict):
            steps = [steps]
            result["steps"] = steps
        if not isinstance(steps, list) or not steps:
            raise ValueError(f"Response missing valid 'steps' list. Got: {type(steps).__name__}")
        return result
    except Exception as exc:
        logger.error("plan_todo_list failed: %s", exc)
        return {
            "steps": [
                {
                    "id": 1,
                    "action": user_task,
                    "target": "screen",
                    "expected_result": "Task accomplished",
                    "needs_user_data": False,
                    "user_data_field": None,
                }
            ],
            "notes": f"Fallback single-step plan (LLM error: {exc})",
            "estimated_complexity": "unknown",
        }


# ---------------------------------------------------------------------------
# 2.  plan_step_hid
# ---------------------------------------------------------------------------

def plan_step_hid(
    screen_data: dict,
    todo_list: List[dict],
    current_step: dict,
    user_task: str,
    model: str = "models/gemini-flash-latest",
) -> dict:
    """
    Generate a HID command sequence for ONE specific step.

    Returns::

        {
          "hid_commands": [
            {"cmd": "mouse_move", "dx": 500, "dy": 300},
            {"cmd": "mouse_click", "button": "left"},
            {"cmd": "type_text", "text": "hello"}
          ],
          "reasoning": "Moving to login button and clicking it"
        }
    """
    screen_text = _screen_to_text(screen_data)
    detected_elements = _extract_elements(screen_data)

    # Build a compact progress overview for the LLM
    steps_overview = "\n".join(
        f"  {'✅' if s.get('status') == 'done' else '▶️ ' if s.get('id') == current_step.get('id') else '⬜'} "
        f"Step {s['id']}: {s['action']}"
        for s in todo_list
    )

    user_data_note = ""
    if current_step.get("user_input"):
        user_data_note = f"\nUser-provided data for this step: {current_step['user_input']}"

    # Build a strict element reference table so the LLM sees exact coords as JSON
    if detected_elements:
        element_table = json.dumps(detected_elements, indent=2)
        element_section = f"""
=== DETECTED ELEMENTS — EXACT COORDINATES (copy dx/dy VERBATIM, do NOT change) ===
{element_table}
"""
    else:
        element_section = "\n=== DETECTED ELEMENTS ===\nNone detected.\n"

    prompt = f"""{SYSTEM_PROMPT}

TASK: Generate HID commands to execute ONE specific step.

=== OVERALL GOAL ===
{user_task}

=== ALL STEPS (context only) ===
{steps_overview}

=== CURRENT STEP ===
  Action:          {current_step['action']}
  Target:          {current_step.get('target', 'see screen')}
  Expected result: {current_step.get('expected_result', 'unknown')}{user_data_note}

=== CURRENT SCREEN (text summary) ===
{screen_text}
{element_section}
=== RULES ===
- Generate commands for the CURRENT STEP only.
- For mouse_move: use the EXACT dx and dy values from the DETECTED ELEMENTS table above.
  Do NOT round, approximate, or guess coordinates — copy the numbers exactly.
- For text entry: first mouse_move + mouse_click to focus the field, then type_text.
- For form submission: end with key_press enter if appropriate.

Respond with ONLY this JSON (no markdown):
{{
  "hid_commands": [
    {{"cmd": "mouse_move", "dx": 323, "dy": 247}},
    {{"cmd": "mouse_click", "button": "left"}}
  ],
  "reasoning": "Moving to the target element and clicking it"
}}"""

    client = GeminiClient()
    try:
        raw = client.generate(
            prompt, model=model, max_tokens=2000, temperature=0.1,
            response_mime_type="application/json",
        )
        logger.debug("plan_step_hid raw response: %s", raw[:600])
        result = _extract_json(raw)
        if "hid_commands" not in result:
            raise ValueError("Response missing 'hid_commands'")

        # Snap any mouse_move coordinates to the exact detected element positions
        # to correct for LLM rounding / hallucination.
        result["hid_commands"] = _snap_to_detected_elements(
            result["hid_commands"], detected_elements
        )
        return result
    except Exception as exc:
        logger.error("plan_step_hid failed: %s", exc)
        return {"hid_commands": [], "reasoning": f"Command generation failed: {exc}"}


# ---------------------------------------------------------------------------
# 3.  evaluate_step_result
# ---------------------------------------------------------------------------

def evaluate_step_result(
    new_screen: dict,
    step: dict,
    user_task: str,
    todo_list: List[dict],
    model: str = "models/gemini-flash-latest",
) -> dict:
    """
    Evaluate whether a step succeeded by examining the new screen state.

    Returns::

        {
          "status": "done" | "retry" | "needs_input" | "fatal_error",
          "confidence": 0.0-1.0,
          "reason": "What is visible on screen",
          "question": "Question to ask user (only for needs_input)",
          "field": "field_name (only for needs_input)"
        }
    """
    screen_text = _screen_to_text(new_screen)

    prompt = f"""{SYSTEM_PROMPT}

TASK: Evaluate whether a step was successfully completed.

=== STEP THAT WAS EXECUTED ===
  Action:          {step['action']}
  Expected result: {step.get('expected_result', 'unknown')}

=== SCREEN STATE AFTER EXECUTION ===
{screen_text}

=== STATUS DEFINITIONS ===
- "done":        Expected result is clearly visible. Step succeeded.
- "retry":       Screen unchanged or in unexpected state. Safe to retry.
- "needs_input": A form/dialog requires data only the user can provide
                 (password, 2-FA code, personal information, file path, etc.).
- "fatal_error": An error dialog blocks all further progress (crash, permission
                 denied, irreversible failure).

Respond with ONLY this JSON (no markdown):
{{
  "status": "done",
  "confidence": 0.9,
  "reason": "Login form is now visible as expected",
  "question": null,
  "field": null
}}

For a needs_input example:
{{
  "status": "needs_input",
  "confidence": 1.0,
  "reason": "Password field is visible and focused",
  "question": "Please enter your account password",
  "field": "password"
}}"""

    client = GeminiClient()
    try:
        raw = client.generate(
            prompt, model=model, max_tokens=600, temperature=0.1,
            response_mime_type="application/json",
        )
        logger.debug("evaluate_step_result raw response: %s", raw[:400])
        result = _extract_json(raw)
        valid = {"done", "retry", "needs_input", "fatal_error"}
        if result.get("status") not in valid:
            raise ValueError(f"Invalid status '{result.get('status')}'")
        return result
    except Exception as exc:
        logger.error("evaluate_step_result failed: %s", exc)
        return {
            "status": "retry",
            "confidence": 0.0,
            "reason": f"Evaluation error: {exc}",
            "question": None,
            "field": None,
        }


# ---------------------------------------------------------------------------
# 4.  generate_final_report
# ---------------------------------------------------------------------------

def generate_final_report(
    final_screen: dict,
    user_task: str,
    todo_list: List[dict],
    model: str = "models/gemini-flash-latest",
) -> dict:
    """
    Generate a final human-readable report after the loop completes.

    Returns::

        {
          "success": true/false,
          "summary": "One-sentence outcome",
          "message": "Full multi-line report",
          "steps_completed": N,
          "steps_failed": N,
          "issues": [...],
          "recommendations": [...]
        }
    """
    screen_text = _screen_to_text(final_screen)
    done = [s for s in todo_list if s.get("status") == "done"]
    failed = [s for s in todo_list if s.get("status") in ("failed", "permanently_failed")]
    total = len(todo_list)

    steps_summary = "\n".join(
        f"  {'✅' if s.get('status') == 'done' else '❌' if s.get('status') in ('failed', 'permanently_failed') else '⏭️'} "
        f"Step {s['id']}: {s['action']}"
        for s in todo_list
    )

    prompt = f"""{SYSTEM_PROMPT}

TASK: Generate a final task-completion report for the user.

=== ORIGINAL TASK ===
{user_task}

=== EXECUTION RESULTS ===
Total steps:  {total}
Completed:    {len(done)}/{total}
Failed:       {len(failed)}/{total}

Steps:
{steps_summary}

=== FINAL SCREEN STATE ===
{screen_text}

=== RULES ===
- "message" should be a multi-line, human-friendly report (use \\n for line breaks).
- Be concise but complete — mention what succeeded and what (if anything) failed.
- "success" is true only if ALL steps completed.

Respond with ONLY this JSON (no markdown):
{{
  "success": {str(len(failed) == 0).lower()},
  "summary": "One-sentence outcome",
  "message": "Full report text here.\\n\\nStep results:\\n...",
  "steps_completed": {len(done)},
  "steps_failed": {len(failed)},
  "issues": [],
  "recommendations": []
}}"""

    client = GeminiClient()
    try:
        raw = client.generate(
            prompt, model=model, max_tokens=1500, temperature=0.2,
            response_mime_type="application/json",
        )
        logger.debug("generate_final_report raw response: %s", raw[:600])
        result = _extract_json(raw)
        return result
    except Exception as exc:
        logger.error("generate_final_report failed: %s", exc)
        success = len(failed) == 0
        return {
            "success": success,
            "summary": f"{'Completed' if success else 'Partially completed'}: {user_task[:80]}",
            "message": (
                f"Task {'completed successfully' if success else 'partially completed'}.\n"
                f"{len(done)}/{total} steps succeeded."
            ),
            "steps_completed": len(done),
            "steps_failed": len(failed),
            "issues": [f"Step {s['id']} failed: {s['action']}" for s in failed],
            "recommendations": [],
        }
