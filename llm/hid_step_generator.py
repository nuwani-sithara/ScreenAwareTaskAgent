"""
HID Step Generator - Converts visual perception + instruction to HID protocol commands

This module takes:
1. Visual perception data (screen elements, bboxes, types, labels)
2. User instruction
3. Generates HID protocol-compliant commands

HID Protocol commands:
- mouse_move: {"cmd":"mouse_move","meta":{"commandId":"uuid"},"dx":10,"dy":-5}
- mouse_click: {"cmd":"mouse_click","meta":{"commandId":"uuid"},"button":"left"}
- type_text: {"cmd":"type_text","meta":{"commandId":"uuid"},"text":"Hello"}
- key_press: {"cmd":"key_press","meta":{"commandId":"uuid"},"key":0x28}
- mouse_scroll: {"cmd":"mouse_scroll","meta":{"commandId":"uuid"},"deltaY":-3}
"""

import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from llm.ollama_client import OllamaClient
import logging

logger = logging.getLogger(__name__)


class HIDStepGenerator:
    def _format_rewritten_steps(self, action_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format action_steps into concise rewritten_steps (step, action, description).
        """
        rewritten = []
        for action in action_steps:
            step_num = action.get("step", 0)
            action_type = action.get("action", "").lower()
            target = action.get("target", "")
            desc = ""
            if action_type == "click":
                desc = f"Click {target}"
            elif action_type == "type_text":
                text = action.get("text", "")
                desc = f"Type '{text}' in {target}" if target else f"Type '{text}'"
            elif action_type == "press_key":
                key = action.get("key", "")
                desc = f"Press {key.upper()} key"
            elif action_type == "wait":
                duration = action.get("duration_ms", 0)
                desc = f"Wait {duration}ms"
            elif action_type == "navigate":
                nav_target = action.get("target", "")
                desc = f"Navigate to {nav_target}"
            else:
                desc = f"{action_type}"
                if target:
                    desc += f" - {target}"
            rewritten.append({
                "step": step_num,
                "action": action_type,
                "description": desc
            })
        return rewritten

    def _generate_command_id(self) -> str:
        """Generate a UUID for command tracking"""
        return str(uuid.uuid4())

    def _create_hid_command(self, cmd_type: str, **params) -> Dict[str, Any]:
        """Create a properly formatted HID protocol command"""
        command = {
            "cmd": cmd_type,
            "meta": {
                "commandId": self._generate_command_id()
            }
        }
        command.update(params)
        return command

    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()
        
        # HID keycode mappings (most common keys)
        self.keycodes = {
            "enter": 0x28,
            "escape": 0x29,
            "backspace": 0x2A,
            "tab": 0x2B,
            "space": 0x2C,
            "up": 0x52,
            "down": 0x51,
            "left": 0x50,
            "right": 0x4F,
            "delete": 0x4C,
            "f1": 0x3A, "f2": 0x3B, "f3": 0x3C, "f4": 0x3D,
            "f5": 0x3E, "f6": 0x3F, "f7": 0x40, "f8": 0x41,
            "f9": 0x42, "f10": 0x43, "f11": 0x44, "f12": 0x45,
        }
    
    def _build_visual_context(self, visual_data: Dict[str, Any]) -> str:
        """Build a concise text description of the screen state for LLM"""
        
        if not visual_data or "session_data" not in visual_data:
            return "No visual data available."
        
        session = visual_data["session_data"]
        screens = session.get("screens", [])
        
        if not screens:
            return "No screens detected."
        
        # Get the latest screen
        latest_screen = screens[-1]
        elements = latest_screen.get("elements", [])
        
        context = f"Screen Elements Detected: {len(elements)}\n\n"
        
        # Filter and describe only relevant elements (buttons, input fields, etc.)
        interactive_elements = []
        for idx, elem in enumerate(elements):
            elem_type = elem.get("type", "unknown")
            label = elem.get("label", "").strip()
            description = elem.get("description", "").strip()
            state = elem.get("state", "unknown")
            confidence = elem.get("confidence", 0)
            elem_id = elem.get("id") or f"elem_{idx}"  # Generate ID if missing
            
            # Handle both coordinate formats:
            # 1. Direct x, y pixel coordinates (new format)
            # 2. Normalized bbox [x1, y1, x2, y2] (old format)
            if "x" in elem and "y" in elem:
                # Direct pixel coordinates
                center_x = elem.get("x", 0)
                center_y = elem.get("y", 0)
            else:
                # Normalized bbox coordinates
                bbox = elem.get("bbox", [])
                if bbox and len(bbox) >= 4:
                    center_x = int((bbox[0] + bbox[2]) / 2 * 1920)
                    center_y = int((bbox[1] + bbox[3]) / 2 * 1080)
                else:
                    center_x, center_y = 0, 0
            
            # Focus on interactive elements or high-confidence ones
            if elem_type in ["button", "input_field", "input", "text", "checkbox", "dropdown"] or confidence >= 0.3:
                elem_info = {
                    "id": elem_id,
                    "type": elem_type,
                    "label": label or description or f"unlabeled {elem_type}",
                    "x": center_x,
                    "y": center_y,
                    "state": state,
                    "confidence": confidence
                }
                interactive_elements.append(elem_info)
        
        # Sort by type priority (buttons and inputs first) then confidence
        type_priority = {"button": 0, "input_field": 1, "text": 2, "checkbox": 3, "dropdown": 4, "unknown": 5}
        interactive_elements.sort(key=lambda x: (type_priority.get(x["type"], 99), -x["confidence"]))
        
        # Build context string with clear positioning and natural language
        for i, elem in enumerate(interactive_elements[:10], 1):  # Top 10 elements
            center_x = elem["x"]
            center_y = elem["y"]
            elem_type = elem['type']
            label = elem['label']
            
            # Use natural language descriptions that match user instructions
            if elem_type in ["input", "input_field"]:
                natural_desc = f"'{label}' input field"
            elif elem_type == "button":
                natural_desc = f"'{label}' button"
            elif elem_type == "text":
                natural_desc = f"Text: '{label}'"
            elif elem_type == "checkbox":
                natural_desc = f"'{label}' checkbox"
            elif elem_type == "dropdown":
                natural_desc = f"'{label}' dropdown"
            else:
                natural_desc = f"{elem_type}: '{label}'"
            
            context += f"{i}. {natural_desc} at position ({center_x}, {center_y})\n"
        
        return context
    
    def validate_instruction_with_visual_context(
        self, 
        instruction: str, 
        visual_data: Dict[str, Any],
        model: str = "mistral"
    ) -> Dict[str, Any]:
        """
        Validate if the user's instruction matches the current visual context.
        Uses LLM to check if required UI elements are present.
        
        Args:
            instruction: User's task instruction
            visual_data: Visual perception data
            model: LLM model to use
            
        Returns:
            {
                "is_valid": bool,
                "confidence": float,
                "reason": str,
                "suggested_actions": List[str],  # If invalid, suggest next steps
                "missing_elements": List[str]
            }
        """
        
        visual_context = self._build_visual_context(visual_data)
        
        # Build validation prompt
        validation_prompt = f"""You are a UI validation assistant. Analyze if the user's instruction matches the current screen content.

CURRENT SCREEN ELEMENTS:
{visual_context}

USER INSTRUCTION:
{instruction}

TASK:
Determine if the instruction can be completed with the currently visible elements.
Match elements by their PURPOSE and LABEL, not exact wording:
- "Username field" matches "Username input field"
- "Password field" matches "Password input field"  
- "Login button" matches "Login button"
- "Click Send" matches "Send button"

Respond ONLY with valid JSON (no comments, no markdown):
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "reason": "Brief explanation",
    "missing_elements": ["list of missing elements if any"],
    "suggested_actions": ["scroll_down", "scroll_up", "wait_for_load", etc. - if elements not found"]
}}

RULES:
- Set is_valid=true if ALL required elements are present (even with slightly different wording)
- Set is_valid=false ONLY if key elements are completely missing from the screen
- Be FLEXIBLE with element names: "Username" and "Username field" and "Username input" all refer to the same thing
- confidence=1.0 means absolutely certain, 0.5 means uncertain
- suggested_actions should help find missing elements (e.g., "scroll_down" if buttons might be below)

JSON Response:"""

        try:
            logger.info("🔍 Validating instruction against visual context...")
            logger.debug(f"Visual Context:\n{visual_context}")
            
            # Get LLM validation
            response = self.client.generate(
                model=model,
                prompt=validation_prompt,
                max_tokens=500,
                temperature=0.3  # Lower temperature for more deterministic validation
            )
            
            # Clean and parse response
            response_text = response.strip()
            
            # Strip markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Strip JSON comments (// and /* */)
            import re
            response_text = re.sub(r'//.*?$', '', response_text, flags=re.MULTILINE)
            response_text = re.sub(r'/\*.*?\*/', '', response_text, flags=re.DOTALL)
            
            validation_result = json.loads(response_text)
            
            is_valid = validation_result.get("is_valid", False)
            confidence = validation_result.get("confidence", 0.5)
            reason = validation_result.get("reason", "")
            
            if is_valid:
                logger.info(f"✅ Validation PASSED (confidence: {confidence:.2f}): {reason}")
            else:
                logger.warning(f"⚠️ Validation FAILED (confidence: {confidence:.2f}): {reason}")
                missing = validation_result.get("missing_elements", [])
                suggested = validation_result.get("suggested_actions", [])
                logger.info(f"   Missing: {missing}")
                logger.info(f"   Suggested: {suggested}")
            
            return validation_result
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse validation response: {e}")
            # Default to proceeding with caution
            return {
                "is_valid": True,  # Assume valid to not block workflow
                "confidence": 0.3,
                "reason": "Unable to validate - proceeding with caution",
                "missing_elements": [],
                "suggested_actions": []
            }
        except Exception as e:
            logger.exception("Validation error")
            return {
                "is_valid": True,
                "confidence": 0.3,
                "reason": f"Validation error: {str(e)}",
                "missing_elements": [],
                "suggested_actions": []
            }
    
    # Only keep the correct _format_rewritten_steps method (the first one)
            
            # Parse different action types
            # Note: Order matters - check CLICK AT before CLICK
            if "CLICK" in upper_line and "AT" in upper_line:
                # Extract element ID or coordinates
                if "elem_" in line:
                    # Format: CLICK elem_4
                    elem_id = None
                    for part in line.split():
                        if part.startswith("elem_"):
                            elem_id = part
                            break
                    
                    if elem_id and elem_id in element_map:
                        elem = element_map[elem_id]
                        bbox = elem.get("bbox", [])
                        if bbox:
                            # Calculate center point
                            center_x = int((bbox[0] + bbox[2]) / 2 * 1920)
                            center_y = int((bbox[1] + bbox[3]) / 2 * 1080)
                            
                            # Add move command first
                            hid_commands.append(self._create_hid_command(
                                "mouse_move",
                                dx=center_x,
                                dy=center_y
                            ))
                            
                            # Then click
                            button = "right" if "RIGHT" in upper_line else "left"
                            hid_commands.append(self._create_hid_command(
                                "mouse_click",
                                button=button
                            ))
                
                elif "AT" in upper_line:
                    # Format: CLICK at (100, 200)
                    import re
                    coords = re.search(r'(\d+)[,\s]+(\d+)', line)
                    if coords:
                        x, y = int(coords.group(1)), int(coords.group(2))
                        hid_commands.append(self._create_hid_command(
                            "mouse_move",
                            dx=x,
                            dy=y
                        ))
                        button = "right" if "RIGHT" in upper_line else "left"
                        hid_commands.append(self._create_hid_command(
                            "mouse_click",
                            button=button
                        ))
            
            elif "TYPE" in upper_line or "ENTER TEXT" in upper_line:
                # Format: TYPE "Hello World" or ENTER TEXT "username"
                # Try to extract quoted text
                text_match = re.search(r'["\']([^"\']+)["\']', line)
                if text_match:
                    text = text_match.group(1)
                    hid_commands.append(self._create_hid_command(
                        "type_text",
                        text=text
                    ))
                else:
                    # Try without quotes - extract text after TYPE/ENTER TEXT
                    text_match = re.search(r'TYPE\s+(.+)', upper_line)
                    if text_match:
                        text = text_match.group(1).strip()
                        # Remove common non-text patterns
                        if text and len(text) > 0 and not text.startswith('('):
                            hid_commands.append(self._create_hid_command(
                                "type_text",
                                text=text
                            ))
            
            elif "MOVE" in upper_line and "TO" in upper_line:
                # Format: MOVE TO 500, 300
                coords = re.search(r'(\d+)[,\s]+(\d+)', line)
                if coords:
                    x, y = int(coords.group(1)), int(coords.group(2))
                    hid_commands.append(self._create_hid_command(
                        "mouse_move",
                        dx=x,
                        dy=y
                    ))
            
            elif "SCROLL" in upper_line:
                # Format: SCROLL UP 3 or SCROLL DOWN 5
                import re
                amount_match = re.search(r'(\d+)', line)
                amount = int(amount_match.group(1)) if amount_match else 1
                if "DOWN" in upper_line:
                    amount = -amount
                hid_commands.append(self._create_hid_command(
                    "mouse_scroll",
                    deltaY=amount
                ))
            
            elif "PRESS" in upper_line and "KEY" in upper_line:
                # Format: PRESS ENTER or PRESS KEY escape or PRESS KEY tab
                matched = False
                for key_name, keycode in self.keycodes.items():
                    if key_name.upper() in upper_line:
                        hid_commands.append(self._create_hid_command(
                            "key_press",
                            key=keycode
                        ))
                        # Also add key release
                        hid_commands.append(self._create_hid_command(
                            "key_release",
                            key=keycode
                        ))
                        matched = True
                        break
                
                # If no specific key matched, log it
                if not matched:
                    logger.warning(f"Unknown key in line: {line}")
            
            elif "WAIT" in upper_line or "DELAY" in upper_line:
                # Format: WAIT 1000ms or DELAY 2s
                time_match = re.search(r'(\d+)', line)
                if time_match:
                    # Store as metadata for execution layer to handle
                    delay_ms = int(time_match.group(1))
                    if 's' in line.lower() and 'ms' not in line.lower():
                        delay_ms *= 1000
                    hid_commands.append({
                        "cmd": "delay",
                        "meta": {"commandId": self._generate_command_id()},
                        "duration_ms": delay_ms
                    })
        
        # Deduplicate consecutive mouse_move commands with same coordinates
        deduplicated = []
        if 'hid_commands' in locals():
            for i, cmd in enumerate(hid_commands):
                # Skip if this is a duplicate mouse_move
                if cmd["cmd"] == "mouse_move" and i > 0:
                    prev_cmd = hid_commands[i - 1]
                    if (prev_cmd["cmd"] == "mouse_move" and 
                        prev_cmd.get("dx") == cmd.get("dx") and 
                        prev_cmd.get("dy") == cmd.get("dy")):
                        # Skip this duplicate move
                        continue
                deduplicated.append(cmd)
        return deduplicated
    
    def generate_action_steps(
        self,
        instruction: str,
        visual_data: Dict[str, Any],
        model: str = "mistral",
        max_tokens: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Stage 1: Generate structured action steps from instruction + visual data
        
        Args:
            instruction: User's task instruction
            visual_data: Visual perception output with screen elements
            model: LLM model to use
            max_tokens: Max tokens for generation
        
        Returns:
            List of structured actions, e.g.:
            [
                {"step": 1, "action": "click", "target": "username field", "x": 863, "y": 475},
                {"step": 2, "action": "type_text", "target": "username field", "text": "admin"},
                {"step": 3, "action": "press_key", "key": "enter"}
            ]
        """
        
        visual_context = self._build_visual_context(visual_data)
        
        prompt = f"""You are a UI automation task planner. Given a screen analysis and user instruction, generate a structured action plan in JSON format.

SCREEN ELEMENTS WITH COORDINATES:
{visual_context}

User Instruction: {instruction}

CRITICAL RULES - READ CAREFULLY:
1. Output ONLY a JSON array of action steps
2. NO explanations, NO markdown, NO code blocks, NO COMMENTS (no // or /* */)
3. For click actions: You MUST COPY the EXACT x, y coordinates shown above
   - Example: If screen shows "username field at position (863, 475)", use "x": 863, "y": 475
   - NEVER use placeholder values like "x": 0, "y": 0
   - ALWAYS look up the coordinates from the screen elements list above
4. Available actions: "click", "type_text", "press_key", "navigate", "wait"
5. For type_text actions: include the text to type
6. For press_key actions: use key names (enter, tab, escape, space, up, down, left, right)

UI INTERACTION PATTERNS:
- Always CLICK an input field BEFORE typing into it (to focus the field)
- For forms: Click field → Type → Click next field → Type → Submit
- For login: Click username → Type username → Click/Tab to password → Type password → Press enter OR Click login button
- Submit buttons are clicked AFTER filling all fields, not before

Action Schema:
{{
  "step": number,
  "action": "click" | "type_text" | "press_key" | "navigate" | "wait",
  "target": "element description",
  "x": number (for click),
  "y": number (for click),
  "text": "string" (for type_text),
  "key": "keyname" (for press_key),
  "duration_ms": number (for wait)
}}

Example for "test the login screen" with username field at (863, 475), password field at (863, 583), login button at (912, 739):
[
  {{"step": 1, "action": "click", "target": "username field", "x": 863, "y": 475}},
  {{"step": 2, "action": "type_text", "target": "username field", "text": "admin"}},
  {{"step": 3, "action": "press_key", "key": "tab"}},
  {{"step": 4, "action": "type_text", "target": "password field", "text": "password123"}},
  {{"step": 5, "action": "press_key", "key": "enter"}}
]

Alternative (using clicks instead of tab/enter):
[
  {{"step": 1, "action": "click", "target": "username field", "x": 863, "y": 475}},
  {{"step": 2, "action": "type_text", "target": "username field", "text": "admin"}},
  {{"step": 3, "action": "click", "target": "password field", "x": 863, "y": 583}},
  {{"step": 4, "action": "type_text", "target": "password field", "text": "password123"}},
  {{"step": 5, "action": "click", "target": "login button", "x": 912, "y": 739}}
]

Now generate the action plan for: {instruction}

Output JSON array:"""

        logger.info(f"Stage 1: Generating action plan for: {instruction[:50]}...")
        
        llm_output = self.client.generate(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            timeout=30
        )
        
        logger.info(f"Stage 1 LLM output:\n{llm_output}")
        
        # Parse JSON output
        try:
            # Strip markdown code blocks if present
            import re
            clean_output = llm_output.strip()
            if "```json" in clean_output:
                match = re.search(r'```json\s*(.*?)\s*```', clean_output, re.DOTALL)
                if match:
                    clean_output = match.group(1)
            elif "```" in clean_output:
                match = re.search(r'```\s*(.*?)\s*```', clean_output, re.DOTALL)
                if match:
                    clean_output = match.group(1)
            
            # Strip JSON comments (// comments)
            # Remove single-line comments like: "x": 0 // comment
            # Match from // up to (but not including) next }, ], or comma
            clean_output = re.sub(r'//[^},\]]*', '', clean_output)
            
            # Remove multi-line comments /* ... */
            clean_output = re.sub(r'/\*.*?\*/', '', clean_output, flags=re.DOTALL)
            
            actions = json.loads(clean_output)
            
            if not isinstance(actions, list):
                logger.error(f"LLM output is not a JSON array: {type(actions)}")
                return []
            
            # Validate coordinates (warn about placeholder values)
            for action in actions:
                if action.get("action") == "click":
                    x = action.get("x", 0)
                    y = action.get("y", 0)
                    if x == 0 and y == 0:
                        logger.warning(f"⚠️ Step {action.get('step')}: Click action has placeholder coordinates (0, 0). LLM should use actual coordinates from visual context!")
            
            logger.info(f"✅ Stage 1: Generated {len(actions)} action steps")
            return actions
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM output as JSON: {e}")
            logger.error(f"Raw output: {llm_output}")
            return []
    
    def convert_actions_to_hid(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Stage 2: Convert structured actions to HID protocol commands
        
        Args:
            actions: List of structured actions from Stage 1
        
        Returns:
            List of HID protocol commands
        """
        
        hid_commands = []
        
        for action in actions:
            action_type = action.get("action", "").lower()
            
            if action_type == "click":
                # Click = mouse_move + mouse_click
                x = action.get("x", 0)
                y = action.get("y", 0)
                
                hid_commands.append(self._create_hid_command(
                    "mouse_move",
                    dx=x,
                    dy=y
                ))
                
                hid_commands.append(self._create_hid_command(
                    "mouse_click",
                    button="left"
                ))
            
            elif action_type == "type_text":
                text = action.get("text", "")
                if text:
                    hid_commands.append(self._create_hid_command(
                        "type_text",
                        text=text
                    ))
            
            elif action_type == "press_key":
                key_name = action.get("key", "").lower()
                if key_name in self.keycodes:
                    keycode = self.keycodes[key_name]
                    
                    # Key press
                    hid_commands.append(self._create_hid_command(
                        "key_press",
                        key=keycode
                    ))
                    
                    # Key release
                    hid_commands.append(self._create_hid_command(
                        "key_release",
                        key=keycode
                    ))
                else:
                    logger.warning(f"Unknown key: {key_name}")
            
            elif action_type == "wait":
                duration_ms = action.get("duration_ms", 1000)
                hid_commands.append({
                    "cmd": "delay",
                    "meta": {"commandId": self._generate_command_id()},
                    "duration_ms": duration_ms
                })
            
            elif action_type == "navigate":
                # Skip navigation actions (not HID commands)
                logger.info(f"Skipping navigation action: {action.get('target')}")
                continue
        
        logger.info(f"✅ Stage 2: Converted {len(actions)} actions to {len(hid_commands)} HID commands")
        return hid_commands
    
    def generate_hid_steps(
        self,
        instruction: str,
        visual_data: Dict[str, Any],
        model: str = "mistral",
        max_tokens: int = 500,
        skip_validation: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point: Generate HID commands using two-stage pipeline
        
        Stage 0: Validate instruction matches visual context (optional)
        Stage 1: Generate structured action steps (JSON)
        Stage 2: Convert actions to HID protocol commands
        
        Args:
            instruction: User's task instruction (e.g., "test the login screen")
            visual_data: Visual perception output with screen elements
            model: LLM model to use
            max_tokens: Max tokens for generation
            skip_validation: Skip validation check (default: False)
        
        Returns:
            {
                "status": "success" | "validation_failed" | "error",
                "instruction": "...",
                "visual_summary": "...",
                "validation": {...},  # Validation result if performed
                "action_steps": [...],  # Stage 1 output
                "hid_commands": [...],   # Stage 2 output
                "total_commands": N,
                "timestamp": "..."
            }
        """
        
        try:
            visual_context = self._build_visual_context(visual_data)
            
            # Stage 0: Validate instruction matches visual context
            validation_result = None
            if not skip_validation:
                validation_result = self.validate_instruction_with_visual_context(
                    instruction=instruction,
                    visual_data=visual_data,
                    model=model
                )
                
                # If validation failed with high confidence, suggest navigation
                if not validation_result.get("is_valid") and validation_result.get("confidence", 0) >= 0.7:
                    logger.warning("⚠️ Validation failed - suggesting navigation actions")
                    return {
                        "status": "validation_failed",
                        "instruction": instruction,
                        "visual_summary": visual_context[:500],
                        "validation": validation_result,
                        "rewritten_steps": [],
                        "action_steps": [],
                        "hid_commands": [],
                        "total_commands": 0,
                        "timestamp": datetime.utcnow().isoformat(),
                        "message": f"Required elements not found on screen. {validation_result.get('reason', '')}",
                        "suggested_actions": validation_result.get("suggested_actions", [])
                    }
            
            # Stage 1: Generate structured action steps
            action_steps = self.generate_action_steps(
                instruction=instruction,
                visual_data=visual_data,
                model=model,
                max_tokens=max_tokens
            )
            
            if not action_steps:
                logger.warning("Stage 1 returned no actions")
                return {
                    "status": "error",
                    "error": "Failed to generate action steps",
                    "instruction": instruction,
                    "visual_summary": visual_context[:500],
                    "validation": validation_result,
                    "rewritten_steps": [],
                    "action_steps": [],
                    "hid_commands": [],
                    "total_commands": 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Stage 2: Convert actions to HID commands
            hid_commands = self.convert_actions_to_hid(action_steps)
            
            # Format action steps into rewritten_steps format
            rewritten_steps = self._format_rewritten_steps(action_steps)
            
            result = {
                "status": "success",
                "instruction": instruction,
                "visual_summary": visual_context[:500],
                "validation": validation_result,  # Include validation result
                "rewritten_steps": rewritten_steps,  # Human-readable steps in structured format
                "action_steps": action_steps,  # Include intermediate representation
                "hid_commands": hid_commands,
                "total_commands": len(hid_commands),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if validation_result:
                logger.info(f"✅ Three-stage pipeline complete: Validation → {len(action_steps)} actions → {len(hid_commands)} HID commands")
            else:
                logger.info(f"✅ Two-stage pipeline complete: {len(action_steps)} actions → {len(hid_commands)} HID commands")
            
            return result
            
        except Exception as e:
            logger.exception("Failed to generate HID steps")
            return {
                "status": "error",
                "error": str(e),
                "instruction": instruction,
                "validation": None,
                "rewritten_steps": [],
                "action_steps": [],
                "hid_commands": [],
                "total_commands": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def format_commands_for_hid(self, commands: List[Dict[str, Any]]) -> str:
        """Format commands as newline-delimited JSON for HID device"""
        return '\n'.join(json.dumps(cmd) for cmd in commands)



# --- Unified LLM-based step generation using interactive_generate.run_interactive ---
def generate_hid_steps_from_visual(
    instruction: str,
    visual_data: Dict[str, Any],
    model: str = "mistral",
    client: Optional[OllamaClient] = None,
    skip_validation: bool = False
) -> Dict[str, Any]:
    """
    Unified function to generate HID steps using LLM-based rewritten_steps from interactive_generate.run_interactive.
    This ensures consistent, structured step generation across all entry points.
    """
    from llm.interactive_generate import run_interactive

    # Step 1: Get rewritten_steps from run_interactive
    llm_result = run_interactive(
        instruction=instruction,
        visual_data=visual_data
    )

    # Step 2: Generate action_steps and hid_commands using HIDStepGenerator
    generator = HIDStepGenerator(client=client)

    # Step 2a: Validation
    validation_result = generator.validate_instruction_with_visual_context(
        instruction=instruction,
        visual_data=visual_data,
        model=model
    )

    # Step 2b: Generate action_steps and hid_commands
    action_steps = generator.generate_action_steps(
        instruction=instruction,
        visual_data=visual_data,
        model=model,
        max_tokens=500
    )
    hid_commands = generator.convert_actions_to_hid(action_steps) if action_steps else []
    total_commands = len(hid_commands) if hid_commands else 0

    # Compose unified result
    result = {
        "status": llm_result.get("status", "success"),
        "instruction": instruction,
        "validation": validation_result,
        "rewritten_steps": llm_result.get("rewritten_steps", []),
        "action_steps": action_steps,
        "hid_commands": hid_commands,
        "total_commands": total_commands,
        "timestamp": llm_result.get("timestamp", datetime.utcnow().isoformat()),
        "execution_time": llm_result.get("execution_time")
    }
    return result


if __name__ == "__main__":
    # Example usage
    sample_visual = {
        "status": "stopped",
        "session_data": {
            "screens": [{
                "screen_index": 0,
                "timestamp": "2026-02-21T14:54:35.957975",
                "elements": [
                    {
                        "id": "elem_1",
                        "type": "button",
                        "label": "Send",
                        "bbox": [0.023, 0.875, 0.237, 0.933],
                        "state": "enabled",
                        "confidence": 0.95
                    },
                    {
                        "id": "elem_4",
                        "type": "input_field",
                        "label": "Message",
                        "bbox": [0.051, 0.381, 0.626, 0.606],
                        "state": "enabled",
                        "confidence": 0.95
                    }
                ]
            }]
        }
    }
    
    result = generate_hid_steps_from_visual(
        instruction="Type 'Hello World' in the message box and click Send",
        visual_data=sample_visual
    )
    
    print(json.dumps(result, indent=2))







#     """
# HID Step Generator - Converts visual perception + instruction to HID protocol commands

# This module takes:
# 1. Visual perception data (screen elements, bboxes, types, labels)
# 2. User instruction
# 3. Generates HID protocol-compliant commands

# HID Protocol commands:
# - mouse_move: {"cmd":"mouse_move","meta":{"commandId":"uuid"},"dx":10,"dy":-5}
# - mouse_click: {"cmd":"mouse_click","meta":{"commandId":"uuid"},"button":"left"}
# - type_text: {"cmd":"type_text","meta":{"commandId":"uuid"},"text":"Hello"}
# - key_press: {"cmd":"key_press","meta":{"commandId":"uuid"},"key":0x28}
# - mouse_scroll: {"cmd":"mouse_scroll","meta":{"commandId":"uuid"},"deltaY":-3}
# """

# import json
# import uuid
# from typing import List, Dict, Any, Optional
# from datetime import datetime
# from llm.ollama_client import OllamaClient
# import logging

# logger = logging.getLogger(__name__)


# class HIDStepGenerator:
#     """Generates HID protocol commands from visual perception and user intent"""
    
#     def __init__(self, client: Optional[OllamaClient] = None):
#         self.client = client or OllamaClient()
        
#         # HID keycode mappings (most common keys)
#         self.keycodes = {
#             "enter": 0x28,
#             "escape": 0x29,
#             "backspace": 0x2A,
#             "tab": 0x2B,
#             "space": 0x2C,
#             "up": 0x52,
#             "down": 0x51,
#             "left": 0x50,
#             "right": 0x4F,
#             "delete": 0x4C,
#             "f1": 0x3A, "f2": 0x3B, "f3": 0x3C, "f4": 0x3D,
#             "f5": 0x3E, "f6": 0x3F, "f7": 0x40, "f8": 0x41,
#             "f9": 0x42, "f10": 0x43, "f11": 0x44, "f12": 0x45,
#         }
    
#     def _build_visual_context(self, visual_data: Dict[str, Any]) -> str:
#         """Build a concise text description of the screen state for LLM"""
        
#         if not visual_data or "session_data" not in visual_data:
#             return "No visual data available."
        
#         session = visual_data["session_data"]
#         screens = session.get("screens", [])
        
#         if not screens:
#             return "No screens detected."
        
#         # Get the latest screen
#         latest_screen = screens[-1]
#         elements = latest_screen.get("elements", [])
        
#         context = f"Screen Elements Detected: {len(elements)}\n\n"
        
#         # Filter and describe only relevant elements (buttons, input fields, etc.)
#         interactive_elements = []
#         for idx, elem in enumerate(elements):
#             elem_type = elem.get("type", "unknown")
#             label = elem.get("label", "").strip()
#             description = elem.get("description", "").strip()
#             state = elem.get("state", "unknown")
#             confidence = elem.get("confidence", 0)
#             elem_id = elem.get("id") or f"elem_{idx}"  # Generate ID if missing
            
#             # Handle both coordinate formats:
#             # 1. Direct x, y pixel coordinates (new format)
#             # 2. Normalized bbox [x1, y1, x2, y2] (old format)
#             if "x" in elem and "y" in elem:
#                 # Direct pixel coordinates
#                 center_x = elem.get("x", 0)
#                 center_y = elem.get("y", 0)
#             else:
#                 # Normalized bbox coordinates
#                 bbox = elem.get("bbox", [])
#                 if bbox and len(bbox) >= 4:
#                     center_x = int((bbox[0] + bbox[2]) / 2 * 1920)
#                     center_y = int((bbox[1] + bbox[3]) / 2 * 1080)
#                 else:
#                     center_x, center_y = 0, 0
            
#             # Focus on interactive elements or high-confidence ones
#             if elem_type in ["button", "input_field", "input", "text", "checkbox", "dropdown"] or confidence >= 0.3:
#                 elem_info = {
#                     "id": elem_id,
#                     "type": elem_type,
#                     "label": label or description or f"unlabeled {elem_type}",
#                     "x": center_x,
#                     "y": center_y,
#                     "state": state,
#                     "confidence": confidence
#                 }
#                 interactive_elements.append(elem_info)
        
#         # Sort by type priority (buttons and inputs first) then confidence
#         type_priority = {"button": 0, "input_field": 1, "text": 2, "checkbox": 3, "dropdown": 4, "unknown": 5}
#         interactive_elements.sort(key=lambda x: (type_priority.get(x["type"], 99), -x["confidence"]))
        
#         # Build context string with clear positioning and natural language
#         for i, elem in enumerate(interactive_elements[:10], 1):  # Top 10 elements
#             center_x = elem["x"]
#             center_y = elem["y"]
#             elem_type = elem['type']
#             label = elem['label']
            
#             # Use natural language descriptions that match user instructions
#             if elem_type in ["input", "input_field"]:
#                 natural_desc = f"'{label}' input field"
#             elif elem_type == "button":
#                 natural_desc = f"'{label}' button"
#             elif elem_type == "text":
#                 natural_desc = f"Text: '{label}'"
#             elif elem_type == "checkbox":
#                 natural_desc = f"'{label}' checkbox"
#             elif elem_type == "dropdown":
#                 natural_desc = f"'{label}' dropdown"
#             else:
#                 natural_desc = f"{elem_type}: '{label}'"
            
#             context += f"{i}. {natural_desc} at position ({center_x}, {center_y})\n"
        
#         return context
    
#     def validate_instruction_with_visual_context(
#         self, 
#         instruction: str, 
#         visual_data: Dict[str, Any],
#         model: str = "mistral"
#     ) -> Dict[str, Any]:
#         """
#         Validate if the user's instruction matches the current visual context.
#         Uses LLM to check if required UI elements are present.
        
#         Args:
#             instruction: User's task instruction
#             visual_data: Visual perception data
#             model: LLM model to use
            
#         Returns:
#             {
#                 "is_valid": bool,
#                 "confidence": float,
#                 "reason": str,
#                 "suggested_actions": List[str],  # If invalid, suggest next steps
#                 "missing_elements": List[str]
#             }
#         """
        
#         visual_context = self._build_visual_context(visual_data)
        
#         # Build validation prompt
#         validation_prompt = f"""You are a UI validation assistant. Analyze if the user's instruction matches the current screen content.

# CURRENT SCREEN ELEMENTS:
# {visual_context}

# USER INSTRUCTION:
# {instruction}

# TASK:
# Determine if the instruction can be completed with the currently visible elements.
# Match elements by their PURPOSE and LABEL, not exact wording:
# - "Username field" matches "Username input field"
# - "Password field" matches "Password input field"  
# - "Login button" matches "Login button"
# - "Click Send" matches "Send button"

# Respond ONLY with valid JSON (no comments, no markdown):
# {{
#     "is_valid": true/false,
#     "confidence": 0.0-1.0,
#     "reason": "Brief explanation",
#     "missing_elements": ["list of missing elements if any"],
#     "suggested_actions": ["scroll_down", "scroll_up", "wait_for_load", etc. - if elements not found"]
# }}

# RULES:
# - Set is_valid=true if ALL required elements are present (even with slightly different wording)
# - Set is_valid=false ONLY if key elements are completely missing from the screen
# - Be FLEXIBLE with element names: "Username" and "Username field" and "Username input" all refer to the same thing
# - confidence=1.0 means absolutely certain, 0.5 means uncertain
# - suggested_actions should help find missing elements (e.g., "scroll_down" if buttons might be below)

# JSON Response:"""

#         try:
#             logger.info("🔍 Validating instruction against visual context...")
#             logger.debug(f"Visual Context:\n{visual_context}")
            
#             # Get LLM validation
#             response = self.client.generate(
#                 model=model,
#                 prompt=validation_prompt,
#                 max_tokens=500,
#                 temperature=0.3  # Lower temperature for more deterministic validation
#             )
            
#             # Clean and parse response
#             response_text = response.strip()
            
#             # Strip markdown code blocks if present
#             if "```json" in response_text:
#                 response_text = response_text.split("```json")[1].split("```")[0].strip()
#             elif "```" in response_text:
#                 response_text = response_text.split("```")[1].split("```")[0].strip()
            
#             # Strip JSON comments (// and /* */)
#             import re
#             response_text = re.sub(r'//.*?$', '', response_text, flags=re.MULTILINE)
#             response_text = re.sub(r'/\*.*?\*/', '', response_text, flags=re.DOTALL)
            
#             validation_result = json.loads(response_text)
            
#             is_valid = validation_result.get("is_valid", False)
#             confidence = validation_result.get("confidence", 0.5)
#             reason = validation_result.get("reason", "")
            
#             if is_valid:
#                 logger.info(f"✅ Validation PASSED (confidence: {confidence:.2f}): {reason}")
#             else:
#                 logger.warning(f"⚠️ Validation FAILED (confidence: {confidence:.2f}): {reason}")
#                 missing = validation_result.get("missing_elements", [])
#                 suggested = validation_result.get("suggested_actions", [])
#                 logger.info(f"   Missing: {missing}")
#                 logger.info(f"   Suggested: {suggested}")
            
#             return validation_result
            
#         except json.JSONDecodeError as e:
#             logger.warning(f"Failed to parse validation response: {e}")
#             # Default to proceeding with caution
#             return {
#                 "is_valid": True,  # Assume valid to not block workflow
#                 "confidence": 0.3,
#                 "reason": "Unable to validate - proceeding with caution",
#                 "missing_elements": [],
#                 "suggested_actions": []
#             }
#         except Exception as e:
#             logger.exception("Validation error")
#             return {
#                 "is_valid": True,
#                 "confidence": 0.3,
#                 "reason": f"Validation error: {str(e)}",
#                 "missing_elements": [],
#                 "suggested_actions": []
#             }
    
#     def _format_action_steps(self, action_steps: List[Dict[str, Any]]) -> List[str]:
#         """
#         Format action steps into human-readable descriptions
        
#         Args:
#             action_steps: List of structured actions from Stage 1
        
#         Returns:
#             List of formatted step descriptions
#         """
#         formatted_steps = []
        
#         for action in action_steps:
#             step_num = action.get("step", 0)
#             action_type = action.get("action", "").lower()
#             target = action.get("target", "")
            
#             # Build human-readable description
#             if action_type == "click":
#                 description = f"Step {step_num}: Click {target}"
                    
#             elif action_type == "type_text":
#                 text = action.get("text", "")
#                 description = f"Step {step_num}: Type '{text}'"
#                 if target:
#                     description += f" in {target}"
                    
#             elif action_type == "press_key":
#                 key = action.get("key", "")
#                 description = f"Step {step_num}: Press {key.upper()} key"
                    
#             elif action_type == "wait":
#                 duration = action.get("duration_ms", 0)
#                 description = f"Step {step_num}: Wait {duration}ms"
                
#             elif action_type == "navigate":
#                 nav_target = action.get("target", "")
#                 description = f"Step {step_num}: Navigate to {nav_target}"
                
#             else:
#                 description = f"Step {step_num}: {action_type}"
#                 if target:
#                     description += f" - {target}"
            
#             formatted_steps.append(description)
        
#         return formatted_steps
    
#     def _generate_command_id(self) -> str:
#         """Generate a UUID for command tracking"""
#         return str(uuid.uuid4())
    
#     def _create_hid_command(self, cmd_type: str, **params) -> Dict[str, Any]:
#         """Create a properly formatted HID protocol command"""
#         command = {
#             "cmd": cmd_type,
#             "meta": {
#                 "commandId": self._generate_command_id()
#             }
#         }
#         command.update(params)
#         return command
    
#     def _parse_llm_steps_to_hid(self, llm_output: str, visual_data: Dict[str, Any]) -> List[Dict[str, Any]]:
#         """
#         Parse LLM output and convert to HID commands.
        
#         Expected LLM output format:
#         1. CLICK element_id (or CLICK button at x,y)
#         2. TYPE "text to type"
#         3. MOVE_TO x,y
#         4. SCROLL direction amount
#         5. PRESS_KEY keyname
#         """
        
#         hid_commands = []
#         import re
        
#         # Remove markdown code blocks if present
#         clean_output = llm_output.strip()
#         if '```' in clean_output:
#             # Extract content from code blocks
#             code_blocks = re.findall(r'```(?:\w+)?\s*\n?(.*?)\n?```', clean_output, re.DOTALL)
#             if code_blocks:
#                 clean_output = '\n'.join(code_blocks)
        
#         # Check if commands are on a single line (no newlines but has multiple commands)
#         # Split by command keywords if they're all on one line
#         if '\n' not in clean_output and any(keyword in clean_output.upper() for keyword in ['MOVE TO', 'TYPE', 'CLICK', 'PRESS KEY', 'WAIT']):
#             # Split before each command keyword
#             patterns = [
#                 r'(MOVE TO)',
#                 r'(CLICK AT)',
#                 r'(CLICK)',
#                 r'(TYPE)',
#                 r'(PRESS KEY)',
#                 r'(SCROLL)',
#                 r'(WAIT)'
#             ]
#             # Insert newlines before command keywords
#             for pattern in patterns:
#                 clean_output = re.sub(pattern, r'\n\1', clean_output, flags=re.IGNORECASE)
#             clean_output = clean_output.strip()
        
#         lines = clean_output.split('\n')
        
#         # Get element lookup for coordinate mapping
#         element_map = {}
#         if visual_data and "session_data" in visual_data:
#             screens = visual_data["session_data"].get("screens", [])
#             if screens:
#                 latest_screen = screens[-1]
#                 elements = latest_screen.get("elements", [])
#                 for elem in elements:
#                     elem_id = elem.get("id")
#                     if elem_id:  # Only add if ID exists
#                         element_map[elem_id] = elem
        
#         for line in lines:
#             line = line.strip()
#             if not line or line.startswith('#') or line.startswith('//'):
#                 continue
            
#             # Remove common prefixes
#             line = line.lstrip('-*•').strip()  # Remove bullet points
#             line = line.lstrip('0123456789.').strip()  # Remove numbering
            
#             # Skip explanatory text in parentheses
#             if line.startswith('(') and line.endswith(')'):
#                 continue
            
#             upper_line = line.upper()
            
#             # Parse different action types
#             # Note: Order matters - check CLICK AT before CLICK
#             if "CLICK" in upper_line and "AT" in upper_line:
#                 # Extract element ID or coordinates
#                 if "elem_" in line:
#                     # Format: CLICK elem_4
#                     elem_id = None
#                     for part in line.split():
#                         if part.startswith("elem_"):
#                             elem_id = part
#                             break
                    
#                     if elem_id and elem_id in element_map:
#                         elem = element_map[elem_id]
#                         bbox = elem.get("bbox", [])
#                         if bbox:
#                             # Calculate center point
#                             center_x = int((bbox[0] + bbox[2]) / 2 * 1920)
#                             center_y = int((bbox[1] + bbox[3]) / 2 * 1080)
                            
#                             # Add move command first
#                             hid_commands.append(self._create_hid_command(
#                                 "mouse_move",
#                                 dx=center_x,
#                                 dy=center_y
#                             ))
                            
#                             # Then click
#                             button = "right" if "RIGHT" in upper_line else "left"
#                             hid_commands.append(self._create_hid_command(
#                                 "mouse_click",
#                                 button=button
#                             ))
                
#                 elif "AT" in upper_line:
#                     # Format: CLICK at (100, 200)
#                     import re
#                     coords = re.search(r'(\d+)[,\s]+(\d+)', line)
#                     if coords:
#                         x, y = int(coords.group(1)), int(coords.group(2))
#                         hid_commands.append(self._create_hid_command(
#                             "mouse_move",
#                             dx=x,
#                             dy=y
#                         ))
#                         button = "right" if "RIGHT" in upper_line else "left"
#                         hid_commands.append(self._create_hid_command(
#                             "mouse_click",
#                             button=button
#                         ))
            
#             elif "TYPE" in upper_line or "ENTER TEXT" in upper_line:
#                 # Format: TYPE "Hello World" or ENTER TEXT "username"
#                 # Try to extract quoted text
#                 text_match = re.search(r'["\']([^"\']+)["\']', line)
#                 if text_match:
#                     text = text_match.group(1)
#                     hid_commands.append(self._create_hid_command(
#                         "type_text",
#                         text=text
#                     ))
#                 else:
#                     # Try without quotes - extract text after TYPE/ENTER TEXT
#                     text_match = re.search(r'TYPE\s+(.+)', upper_line)
#                     if text_match:
#                         text = text_match.group(1).strip()
#                         # Remove common non-text patterns
#                         if text and len(text) > 0 and not text.startswith('('):
#                             hid_commands.append(self._create_hid_command(
#                                 "type_text",
#                                 text=text
#                             ))
            
#             elif "MOVE" in upper_line and "TO" in upper_line:
#                 # Format: MOVE TO 500, 300
#                 coords = re.search(r'(\d+)[,\s]+(\d+)', line)
#                 if coords:
#                     x, y = int(coords.group(1)), int(coords.group(2))
#                     hid_commands.append(self._create_hid_command(
#                         "mouse_move",
#                         dx=x,
#                         dy=y
#                     ))
            
#             elif "SCROLL" in upper_line:
#                 # Format: SCROLL UP 3 or SCROLL DOWN 5
#                 import re
#                 amount_match = re.search(r'(\d+)', line)
                
#                 if "DOWN" in upper_line:
#                     amount = -amount
                
#                 hid_commands.append(self._create_hid_command(
#                     "mouse_scroll",
#                     deltaY=amount
#                 ))
            
#             elif "PRESS" in upper_line and "KEY" in upper_line:
#                 # Format: PRESS ENTER or PRESS KEY escape or PRESS KEY tab
#                 matched = False
#                 for key_name, keycode in self.keycodes.items():
#                     if key_name.upper() in upper_line:
#                         hid_commands.append(self._create_hid_command(
#                             "key_press",
#                             key=keycode
#                         ))
#                         # Also add key release
#                         hid_commands.append(self._create_hid_command(
#                             "key_release",
#                             key=keycode
#                         ))
#                         matched = True
#                         break
                
#                 # If no specific key matched, log it
#                 if not matched:
#                     logger.warning(f"Unknown key in line: {line}")
            
#             elif "WAIT" in upper_line or "DELAY" in upper_line:
#                 # Format: WAIT 1000ms or DELAY 2s
#                 time_match = re.search(r'(\d+)', line)
#                 if time_match:
#                     # Store as metadata for execution layer to handle
#                     delay_ms = int(time_match.group(1))
#                     if 's' in line.lower() and 'ms' not in line.lower():
#                         delay_ms *= 1000
#                     hid_commands.append({
#                         "cmd": "delay",
#                         "meta": {"commandId": self._generate_command_id()},
#                         "duration_ms": delay_ms
#                     })
        
#         # Deduplicate consecutive mouse_move commands with same coordinates
#         deduplicated = []
#         for i, cmd in enumerate(hid_commands):
#             # Skip if this is a duplicate mouse_move
#             if cmd["cmd"] == "mouse_move" and i > 0:
#                 prev_cmd = hid_commands[i - 1]
#                 if (prev_cmd["cmd"] == "mouse_move" and 
#                     prev_cmd.get("dx") == cmd.get("dx") and 
#                     prev_cmd.get("dy") == cmd.get("dy")):
#                     # Skip this duplicate move
#                     continue
#             deduplicated.append(cmd)
        
#         return deduplicated
    
#     def generate_action_steps(
#         self,
#         instruction: str,
#         visual_data: Dict[str, Any],
#         model: str = "mistral",
#         max_tokens: int = 500
#     ) -> List[Dict[str, Any]]:
#         """
#         Stage 1: Generate structured action steps from instruction + visual data
        
#         Args:
#             instruction: User's task instruction
#             visual_data: Visual perception output with screen elements
#             model: LLM model to use
#             max_tokens: Max tokens for generation
        
#         Returns:
#             List of structured actions, e.g.:
#             [
#                 {"step": 1, "action": "click", "target": "username field", "x": 863, "y": 475},
#                 {"step": 2, "action": "type_text", "target": "username field", "text": "admin"},
#                 {"step": 3, "action": "press_key", "key": "enter"}
#             ]
#         """
        
#         visual_context = self._build_visual_context(visual_data)
        
#         prompt = f"""You are a UI automation task planner. Given a screen analysis and user instruction, generate a structured action plan in JSON format.

# SCREEN ELEMENTS WITH COORDINATES:
# {visual_context}

# User Instruction: {instruction}

# CRITICAL RULES - READ CAREFULLY:
# 1. Output ONLY a JSON array of action steps
# 2. NO explanations, NO markdown, NO code blocks, NO COMMENTS (no // or /* */)
# 3. For click actions: You MUST COPY the EXACT x, y coordinates shown above
#    - Example: If screen shows "username field at position (863, 475)", use "x": 863, "y": 475
#    - NEVER use placeholder values like "x": 0, "y": 0
#    - ALWAYS look up the coordinates from the screen elements list above
# 4. Available actions: "click", "type_text", "press_key", "navigate", "wait"
# 5. For type_text actions: include the text to type
# 6. For press_key actions: use key names (enter, tab, escape, space, up, down, left, right)

# UI INTERACTION PATTERNS:
# - Always CLICK an input field BEFORE typing into it (to focus the field)
# - For forms: Click field → Type → Click next field → Type → Submit
# - For login: Click username → Type username → Click/Tab to password → Type password → Press enter OR Click login button
# - Submit buttons are clicked AFTER filling all fields, not before

# Action Schema:
# {{
#   "step": number,
#   "action": "click" | "type_text" | "press_key" | "navigate" | "wait",
#   "target": "element description",
#   "x": number (for click),
#   "y": number (for click),
#   "text": "string" (for type_text),
#   "key": "keyname" (for press_key),
#   "duration_ms": number (for wait)
# }}

# Example for "test the login screen" with username field at (863, 475), password field at (863, 583), login button at (912, 739):
# [
#   {{"step": 1, "action": "click", "target": "username field", "x": 863, "y": 475}},
#   {{"step": 2, "action": "type_text", "target": "username field", "text": "admin"}},
#   {{"step": 3, "action": "press_key", "key": "tab"}},
#   {{"step": 4, "action": "type_text", "target": "password field", "text": "password123"}},
#   {{"step": 5, "action": "press_key", "key": "enter"}}
# ]

# Alternative (using clicks instead of tab/enter):
# [
#   {{"step": 1, "action": "click", "target": "username field", "x": 863, "y": 475}},
#   {{"step": 2, "action": "type_text", "target": "username field", "text": "admin"}},
#   {{"step": 3, "action": "click", "target": "password field", "x": 863, "y": 583}},
#   {{"step": 4, "action": "type_text", "target": "password field", "text": "password123"}},
#   {{"step": 5, "action": "click", "target": "login button", "x": 912, "y": 739}}
# ]

# Now generate the action plan for: {instruction}

# Output JSON array:"""

#         logger.info(f"Stage 1: Generating action plan for: {instruction[:50]}...")
        
#         llm_output = self.client.generate(
#             prompt=prompt,
#             model=model,
#             max_tokens=max_tokens,
#             timeout=30
#         )
        
#         logger.info(f"Stage 1 LLM output:\n{llm_output}")
        
#         # Parse JSON output
#         try:
#             # Strip markdown code blocks if present
#             import re
#             clean_output = llm_output.strip()
#             if "```json" in clean_output:
#                 match = re.search(r'```json\s*(.*?)\s*```', clean_output, re.DOTALL)
#                 if match:
#                     clean_output = match.group(1)
#             elif "```" in clean_output:
#                 match = re.search(r'```\s*(.*?)\s*```', clean_output, re.DOTALL)
#                 if match:
#                     clean_output = match.group(1)
            
#             # Strip JSON comments (// comments)
#             # Remove single-line comments like: "x": 0 // comment
#             # Match from // up to (but not including) next }, ], or comma
#             clean_output = re.sub(r'//[^},\]]*', '', clean_output)
            
#             # Remove multi-line comments /* ... */
#             clean_output = re.sub(r'/\*.*?\*/', '', clean_output, flags=re.DOTALL)
            
#             actions = json.loads(clean_output)
            
#             if not isinstance(actions, list):
#                 logger.error(f"LLM output is not a JSON array: {type(actions)}")
#                 return []
            
#             # Validate coordinates (warn about placeholder values)
#             for action in actions:
#                 if action.get("action") == "click":
#                     x = action.get("x", 0)
#                     y = action.get("y", 0)
#                     if x == 0 and y == 0:
#                         logger.warning(f"⚠️ Step {action.get('step')}: Click action has placeholder coordinates (0, 0). LLM should use actual coordinates from visual context!")
            
#             logger.info(f"✅ Stage 1: Generated {len(actions)} action steps")
#             return actions
            
#         except json.JSONDecodeError as e:
#             logger.error(f"Failed to parse LLM output as JSON: {e}")
#             logger.error(f"Raw output: {llm_output}")
#             return []
    
#     def convert_actions_to_hid(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#         """
#         Stage 2: Convert structured actions to HID protocol commands
        
#         Args:
#             actions: List of structured actions from Stage 1
        
#         Returns:
#             List of HID protocol commands
#         """
        
#         hid_commands = []
        
#         for action in actions:
#             action_type = action.get("action", "").lower()
            
#             if action_type == "click":
#                 # Click = mouse_move + mouse_click
#                 x = action.get("x", 0)
#                 y = action.get("y", 0)
                
#                 hid_commands.append(self._create_hid_command(
#                     "mouse_move",
#                     dx=x,
#                     dy=y
#                 ))
                
#                 hid_commands.append(self._create_hid_command(
#                     "mouse_click",
#                     button="left"
#                 ))
            
#             elif action_type == "type_text":
#                 text = action.get("text", "")
#                 if text:
#                     hid_commands.append(self._create_hid_command(
#                         "type_text",
#                         text=text
#                     ))
            
#             elif action_type == "press_key":
#                 key_name = action.get("key", "").lower()
#                 if key_name in self.keycodes:
#                     keycode = self.keycodes[key_name]
                    
#                     # Key press
#                     hid_commands.append(self._create_hid_command(
#                         "key_press",
#                         key=keycode
#                     ))
                    
#                     # Key release
#                     hid_commands.append(self._create_hid_command(
#                         "key_release",
#                         key=keycode
#                     ))
#                 else:
#                     logger.warning(f"Unknown key: {key_name}")
            
#             elif action_type == "wait":
#                 duration_ms = action.get("duration_ms", 1000)
#                 hid_commands.append({
#                     "cmd": "delay",
#                     "meta": {"commandId": self._generate_command_id()},
#                     "duration_ms": duration_ms
#                 })
            
#             elif action_type == "navigate":
#                 # Skip navigation actions (not HID commands)
#                 logger.info(f"Skipping navigation action: {action.get('target')}")
#                 continue
        
#         logger.info(f"✅ Stage 2: Converted {len(actions)} actions to {len(hid_commands)} HID commands")
#         return hid_commands
    
#     def generate_hid_steps(
#         self,
#         instruction: str,
#         visual_data: Dict[str, Any],
#         model: str = "mistral",
#         max_tokens: int = 500,
#         skip_validation: bool = False
#     ) -> Dict[str, Any]:
#         """
#         Main entry point: Generate HID commands using two-stage pipeline
        
#         Stage 0: Validate instruction matches visual context (optional)
#         Stage 1: Generate structured action steps (JSON)
#         Stage 2: Convert actions to HID protocol commands
        
#         Args:
#             instruction: User's task instruction (e.g., "test the login screen")
#             visual_data: Visual perception output with screen elements
#             model: LLM model to use
#             max_tokens: Max tokens for generation
#             skip_validation: Skip validation check (default: False)
        
#         Returns:
#             {
#                 "status": "success" | "validation_failed" | "error",
#                 "instruction": "...",
#                 "visual_summary": "...",
#                 "validation": {...},  # Validation result if performed
#                 "action_steps": [...],  # Stage 1 output
#                 "hid_commands": [...],   # Stage 2 output
#                 "total_commands": N,
#                 "timestamp": "..."
#             }
#         """
        
#         try:
#             visual_context = self._build_visual_context(visual_data)
            
#             # Stage 0: Validate instruction matches visual context
#             validation_result = None
#             if not skip_validation:
#                 validation_result = self.validate_instruction_with_visual_context(
#                     instruction=instruction,
#                     visual_data=visual_data,
#                     model=model
#                 )
                
#                 # If validation failed with high confidence, suggest navigation
#                 if not validation_result.get("is_valid") and validation_result.get("confidence", 0) >= 0.7:
#                     logger.warning("⚠️ Validation failed - suggesting navigation actions")
#                     return {
#                         "status": "validation_failed",
#                         "instruction": instruction,
#                         "visual_summary": visual_context[:500],
#                         "validation": validation_result,
#                         "steps_description": [],
#                         "action_steps": [],
#                         "hid_commands": [],
#                         "total_commands": 0,
#                         "timestamp": datetime.utcnow().isoformat(),
#                         "message": f"Required elements not found on screen. {validation_result.get('reason', '')}",
#                         "suggested_actions": validation_result.get("suggested_actions", [])
#                     }
            
#             # Stage 1: Generate structured action steps
#             action_steps = self.generate_action_steps(
#                 instruction=instruction,
#                 visual_data=visual_data,
#                 model=model,
#                 max_tokens=max_tokens
#             )
            
#             if not action_steps:
#                 logger.warning("Stage 1 returned no actions")
#                 return {
#                     "status": "error",
#                     "error": "Failed to generate action steps",
#                     "instruction": instruction,
#                     "visual_summary": visual_context[:500],
#                     "validation": validation_result,
#                     "steps_description": [],
#                     "action_steps": [],
#                     "hid_commands": [],
#                     "total_commands": 0,
#                     "timestamp": datetime.utcnow().isoformat()
#                 }
            
#             # Stage 2: Convert actions to HID commands
#             hid_commands = self.convert_actions_to_hid(action_steps)
            
#             # Format action steps into human-readable descriptions
#             steps_description = self._format_action_steps(action_steps)
            
#             result = {
#                 "status": "success",
#                 "instruction": instruction,
#                 "visual_summary": visual_context[:500],
#                 "validation": validation_result,  # Include validation result
#                 "steps_description": steps_description,  # Human-readable steps
#                 "action_steps": action_steps,  # Include intermediate representation
#                 "hid_commands": hid_commands,
#                 "total_commands": len(hid_commands),
#                 "timestamp": datetime.utcnow().isoformat()
#             }
            
#             if validation_result:
#                 logger.info(f"✅ Three-stage pipeline complete: Validation → {len(action_steps)} actions → {len(hid_commands)} HID commands")
#             else:
#                 logger.info(f"✅ Two-stage pipeline complete: {len(action_steps)} actions → {len(hid_commands)} HID commands")
            
#             return result
            
#         except Exception as e:
#             logger.exception("Failed to generate HID steps")
#             return {
#                 "status": "error",
#                 "error": str(e),
#                 "instruction": instruction,
#                 "validation": None,
#                 "steps_description": [],
#                 "action_steps": [],
#                 "hid_commands": [],
#                 "total_commands": 0,
#                 "timestamp": datetime.utcnow().isoformat()
#             }
    
#     def format_commands_for_hid(self, commands: List[Dict[str, Any]]) -> str:
#         """Format commands as newline-delimited JSON for HID device"""
#         return '\n'.join(json.dumps(cmd) for cmd in commands)



def generate_hid_steps_from_visual(
    instruction: str,
    visual_data: Dict[str, Any],
    model: str = "mistral",
    client=None,
    skip_validation: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to generate HID steps.
    Usage:
        result = generate_hid_steps_from_visual(
            instruction="Click the Send button",
            visual_data=perception_output,
            model="mistral",
            skip_validation=False  # Set to True to skip validation
        )
        hid_commands = result["hid_commands"]
        # Send to HID device
    """
    generator = HIDStepGenerator(client=client)
    return generator.generate_hid_steps(instruction, visual_data, model, skip_validation=skip_validation)


# if __name__ == "__main__":
#     # Example usage
#     sample_visual = {
#         "status": "stopped",
#         "session_data": {
#             "screens": [{
#                 "screen_index": 0,
#                 "timestamp": "2026-02-21T14:54:35.957975",
#                 "elements": [
#                     {
#                         "id": "elem_1",
#                         "type": "button",
#                         "label": "Send",
#                         "bbox": [0.023, 0.875, 0.237, 0.933],
#                         "state": "enabled",
#                         "confidence": 0.95
#                     },
#                     {
#                         "id": "elem_4",
#                         "type": "input_field",
#                         "label": "Message",
#                         "bbox": [0.051, 0.381, 0.626, 0.606],
#                         "state": "enabled",
#                         "confidence": 0.95
#                     }
#                 ]
#             }]
#         }
#     }
    
#     result = generate_hid_steps_from_visual(
#         instruction="Type 'Hello World' in the message box and click Send",
#         visual_data=sample_visual
#     )
    
#     print(json.dumps(result, indent=2))
