import argparse
import json
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional

from llm import ollama_adapter
try:
    from llm.flan_t5_rewriter import rewrite_steps as flan_rewrite
except Exception:
    from llm.simple_rewriter import rewrite_steps as flan_rewrite

from llm.step_validators import StepQualityValidator
from llm.hid_step_generator import HIDStepGenerator
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

OUT_PATH = Path("llm/interactive_results.json")
ESP32_OUT = Path("llm/esp32_steps.jsonl")
SELECTION_REPORT = Path("llm/selection_report.json")
DISPLAY_OUT = Path("llm/esp32_display.jsonl")


def summarize_steps(steps):
    seen_move = False
    out = []
    for s in steps:
        a = (s.get("action") or s.get("description") or "").strip() if isinstance(s, dict) else str(s).strip()
        if not a:
            continue
        low = a.lower()
        if ("new game" in low) or ("start" in low and "game" in low):
            out.append({"step": len(out) + 1, "action": "Start", "description": "Create new game"})
            continue
        if any(k in low for k in ["left arrow", "right arrow", "up arrow", "down arrow", "press left", "press right", "press up", "press down", "arrow key", "arrow"]) or re.search(r"\b(move|slide)\b", low):
            if not seen_move:
                seen_move = True
                out.append({"step": len(out) + 1, "action": "Move Tiles", "description": "Use arrow keys to move tiles toward merges"})
            continue
        if "merge" in low or "combine" in low:
            out.append({"step": len(out) + 1, "action": "Merge Tiles", "description": "If two tiles of the same value touch, they merge into a higher-value tile"})
            continue
        if "rotate" in low or "clockwise" in low or "counterclockwise" in low:
            out.append({"step": len(out) + 1, "action": "Rotate", "description": "Rotate tiles or change orientation if supported"})
            continue
        if "score" in low:
            out.append({"step": len(out) + 1, "action": "Check Score", "description": "View current score on the game board"})
            continue
        if "restart" in low or "refresh" in low or "game over" in low:
            out.append({"step": len(out) + 1, "action": "Game Over", "description": "If no merges remain the game ends; restart to play again"})
            continue
        first_clause = a.split(".")[0]
        out.append({"step": len(out) + 1, "action": first_clause, "description": a})
    return out


def select_steps(original, rewritten):
    tau = 0.55
    orig_q = float(original.get("quality", 0.0))
    rew_q = float(rewritten.get("quality", 0.0))
    orig_conf = float(original.get("confidence", 0.0))
    rew_conf = float(rewritten.get("confidence", 1.0))
    if rew_q >= orig_q or rew_conf >= tau:
        return rewritten.get("steps", []), "rewritten"
    if orig_conf >= tau:
        return original.get("steps", []), "original"
    return rewritten.get("steps", []), "rewritten"


def force_imperative(steps):
    """Heuristic fixer: ensure each step `action` starts with a verb.
    This is a lightweight fallback when the validator fails.
    """
    verb_map = {
        "open": ["open", "navigate", "go to", "visit", "launch"],
        "click": ["click", "tap", "press", "select", "initiate"],
        "upload": ["upload", "choose file", "select file", "pick"],
        "save": ["save", "confirm", "apply"],
        "wait": ["wait", "loading", "uploading"],
        "enter": ["enter", "input", "type", "fill"],
        "verify": ["verify", "check", "validate", "ensure"],
    }

    def pick_verb(text):
        low = text.lower()
        for v, kws in verb_map.items():
            for kw in kws:
                if kw in low:
                    return v.capitalize()
        # Check if it already starts with a verb
        if re.match(r'^(open|click|enter|type|verify|check|select|navigate|launch|tap|press|input|fill|validate)\b', low):
            return None  # Already has a verb
        return "Click"

    fixed = []
    for i, s in enumerate(steps):
        if isinstance(s, dict):
            act = (s.get("action") or "").strip()
            desc = (s.get("description") or "").strip()
            
            # Clean numbering prefixes
            act = re.sub(r'^\d+\.\s*', '', act)
            act = re.sub(r'^Step\s+\d+:\s*', '', act, flags=re.IGNORECASE)
            
            if re.match(r"^[A-Za-z]+\b", act):
                # Check if it already starts with a verb
                verb = pick_verb(act)
                if verb:
                    new_act = f"{verb} {act}"
                else:
                    new_act = act
            else:
                verb = pick_verb(act or desc)
                new_act = f"{verb} {act}" if act else f"{verb}"
            
            fixed.append({"step": s.get("step", i + 1), "action": new_act, "description": desc})
        else:
            text = str(s).strip()
            text = re.sub(r'^\d+\.\s*', '', text)
            verb = pick_verb(text)
            new_act = f"{verb} {text}" if (verb and text) else text
            fixed.append({"step": i + 1, "action": new_act, "description": ""})
    return fixed


def build_better_prompt(instruction: str, visual_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a better prompt for step generation with visual context and clear formatting.
    
    Args:
        instruction: User's task instruction
        visual_data: Optional visual perception data with screen elements
    
    Returns:
        Optimized prompt for LLM
    """
    
    base_prompt = """You are a UI automation task planner. Generate clear, executable step-by-step instructions.

TASK: {instruction}

RULES:
1. Output ONLY a JSON array of action steps
2. NO explanations, NO markdown, NO code blocks, NO comments
3. Each step must start with an action verb (Click, Type, Press, Wait, Navigate, etc.)
4. Steps should be executable in order
5. Keep each step concise (under 100 characters)
6. Include coordinates when available for click actions
7. For text input, specify exact text to type
8. The task must be done successfully, all steps must be generated

HID PROTOCOL CAPABILITIES:
The following actions will be converted to HID protocol commands:
- Click actions → mouse_move (to coordinates) + mouse_click (left/right/middle button)
- Type actions → type_text (sends text string to device)
- Key press → key_press (sends specific keycode: enter=0x28, tab=0x2B, escape=0x29, backspace=0x2A, space=0x2C, arrows=0x4F-0x52, F1-F12=0x3A-0x45)
- Key release → key_release (releases specific key or all keys if no key specified)
- Scroll actions → mouse_scroll (deltaY for vertical, deltaX for horizontal scroll)
- System control → system (media keys like volume, play/pause - code 0-65535, partially supported)
- Wait/Delay → delay (duration in milliseconds for timing control)

OUTPUT FORMAT:
[
  {{
    "step": 1,
    "action": "action_verb",
    "target": "element_description",
    "description": "clear instruction text",
    "x": integer (optional, for clicks),
    "y": integer (optional, for clicks),
    "text": "text_to_type" (optional, for type actions),
    "key": "key_name" (optional, for key presses)
  }}
]

EXAMPLES:

Example 1: "Open Chrome and search for Python"
[
  {{"step": 1, "action": "Click", "target": "Chrome icon", "description": "Click on Chrome browser icon", "x": 150, "y": 300}},
  {{"step": 2, "action": "Wait", "target": "browser", "description": "Wait for Chrome to load", "duration_ms": 2000}},
  {{"step": 3, "action": "Click", "target": "address bar", "description": "Click in the address bar", "x": 500, "y": 100}},
  {{"step": 4, "action": "Type", "target": "address bar", "description": "Type the search URL", "text": "https://www.google.com"}},
  {{"step": 5, "action": "Press", "target": "keyboard", "description": "Press Enter to navigate", "key": "enter"}}
]

Example 2: "Login to the application"
[
  {{"step": 1, "action": "Click", "target": "username field", "description": "Click in the username input field", "x": 863, "y": 475}},
  {{"step": 2, "action": "Type", "target": "username field", "description": "Type username", "text": "admin"}},
  {{"step": 3, "action": "Click", "target": "password field", "description": "Click in the password field", "x": 863, "y": 583}},
  {{"step": 4, "action": "Type", "target": "password field", "description": "Type password", "text": "password123"}},
  {{"step": 5, "action": "Click", "target": "login button", "description": "Click the login button", "x": 912, "y": 739}}
]

"""

    # Add visual context if available
    if visual_data:
        generator = HIDStepGenerator()
        visual_context = generator._build_visual_context(visual_data)
        
        visual_section = f"""
CURRENT SCREEN ELEMENTS WITH COORDINATES:
{visual_context}

IMPORTANT: Use the EXACT coordinates from the screen elements above for click actions.
Match element descriptions to the actual UI elements shown.

"""
        prompt = base_prompt + visual_section + f"Now generate steps for: {instruction}\n\nOutput JSON array:"
    else:
        # Simplified version for no visual data
        simple_prompt = f"""
{base_prompt}
Now generate steps for: {instruction}

Remember: Output ONLY a JSON array, no other text.
"""
        prompt = simple_prompt
    
    return prompt


def run_interactive(
    instruction: str | None = None, 
    show_validation: bool = False, 
    silent: bool = False,
    visual_data: Optional[Dict[str, Any]] = None,
    skip_validation: bool = False,
    use_better_prompt: bool = True  # New flag to use better prompt
):
    """
    Run interactive step generation with improved prompting.
    
    Args:
        instruction: User instruction text
        show_validation: Show validation details
        silent: Suppress console output
        visual_data: Optional visual perception data for HID generation
        skip_validation: Skip visual validation check
        use_better_prompt: Use the improved prompt with examples and structure
        
    Returns:
        If visual_data provided: HID commands with validation
        If no visual_data: Abstract steps (original behavior)
    """
    
    # ============================================================
    # VISUAL-AWARE HID GENERATION MODE (with better prompt)
    # ============================================================
    if visual_data is not None:
        logger.info("🎯 Visual-aware LLM step generation mode enabled")

        if instruction is None:
            instruction = input("Enter instruction: ")

        if not instruction or not instruction.strip():
            logger.warning("No instruction provided")
            return {"error": "No instruction provided"}

        # Use the better prompt builder
        if use_better_prompt:
            prompt = build_better_prompt(instruction, visual_data)
            logger.info("⏳ Using enhanced prompt with examples and structure")
        else:
            # Fallback to original simple prompt
            generator = HIDStepGenerator()
            visual_context = generator._build_visual_context(visual_data)
            prompt = f"""You are given the following screen elements:\n{visual_context}\n\nInstruction: \"{instruction}\"\n\nWrite clear, step-by-step instructions for the user to accomplish the task using only the elements visible on the screen.\n"""

        logger.info(f"⏳ Generating visual-aware steps from LLM for: {instruction[:60]}...")
        
        # Generate with higher token limit for better quality
        gen = ollama_adapter.generate_and_format(
            prompt, 
            max_tokens=1500,  
            timeout=60         
        )
        
        raw_text = gen.get("cleaned_text") or gen.get("raw_output") or ""

        if not raw_text:
            logger.error("Model returned empty response")
            return {"error": "Model returned empty response"}

        import re
        
        # Try to parse JSON if better prompt was used
        steps_raw = []
        if use_better_prompt:
            # Try to extract JSON array from response
            try:
                # Look for JSON array pattern
                json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    steps_raw = json.loads(json_str)
                    logger.info(f"✅ Successfully parsed JSON response with {len(steps_raw)} steps")
            except (json.JSONDecodeError, AttributeError) as e:
                logger.warning(f"Failed to parse JSON response, falling back to text extraction: {e}")
        
        # Fallback to text extraction if JSON parsing failed
        if not steps_raw:
            try:
                steps_raw = ollama_adapter._extract_steps_from_text(raw_text)
            except Exception:
                steps_raw = [
                    {"step": i + 1, "action": line.strip(), "description": ""}
                    for i, line in enumerate(raw_text.splitlines())
                    if line.strip()
                ]

        # Process and clean steps
        rewritten_steps = []
        for step in steps_raw:
            if isinstance(step, dict):
                # Clean up step
                clean_step = {}
                clean_step["step"] = step.get("step", len(rewritten_steps) + 1)
                
                # Get action or build from description
                action = step.get("action", "").strip()
                description = step.get("description", step.get("action", "")).strip()
                
                # Clean numbering prefixes
                action = re.sub(r'^\d+\.\s*', '', action)
                action = re.sub(r'^Step\s+\d+:\s*', '', action, flags=re.IGNORECASE)
                description = re.sub(r'^\d+\.\s*', '', description)
                description = re.sub(r'^Step\s+\d+:\s*', '', description, flags=re.IGNORECASE)
                
                clean_step["action"] = action or description.split()[0] if description else "Click"
                clean_step["description"] = description or action
                
                # Preserve additional fields if present
                if "x" in step and "y" in step:
                    clean_step["x"] = step["x"]
                    clean_step["y"] = step["y"]
                if "text" in step:
                    clean_step["text"] = step["text"]
                if "key" in step:
                    clean_step["key"] = step["key"]
                if "duration_ms" in step:
                    clean_step["duration_ms"] = step["duration_ms"]
                
                rewritten_steps.append(clean_step)
            else:
                # Handle string steps
                text = str(step).strip()
                text = re.sub(r'^\d+\.\s*', '', text)
                rewritten_steps.append({
                    "step": len(rewritten_steps) + 1,
                    "action": text.split()[0] if text else "Click",
                    "description": text
                })

        logger.info(f"✅ Generated {len(rewritten_steps)} visual-aware steps from LLM")

        return {
            "status": "success",
            "instruction": instruction,
            "rewritten_steps": rewritten_steps,
            "raw_text": raw_text,
            "visual_summary": generator._build_visual_context(visual_data)[:500] if 'generator' in locals() else "",
            "timestamp": time.time(),
        }
    
    # ============================================================
    # ABSTRACT STEP GENERATION MODE (NO VISUAL DATA)
    # ============================================================
    if instruction is None:
        instr = input("Enter instruction: ")
    else:
        instr = instruction

    if not instr or not instr.strip():
        logger.warning("No instruction provided")
        return {"error": "No instruction provided"}

    # Always show progress, even in silent mode
    logger.info("⏳ [1/5] Preparing prompt for: %s", instr[:50] + "..." if len(instr) > 50 else instr)

    # --------------------------------------------------
    # 1️⃣ USE BETTER PROMPT (if enabled)
    # --------------------------------------------------
    if use_better_prompt:
        logger.info("Using enhanced prompt with examples and structure")
        prompt = build_better_prompt(instr)
    else:
        # Original minimal prompt
        prompt = f"""Task: "{instr}"

Write SHORT steps (one line each, no sub-points):
1. Open page
2. Enter username
3. Enter password
4. Click login
5. Verify success

Your steps:"""

    # --------------------------------------------------
    # 2️⃣ GENERATE (OLLAMA)
    # --------------------------------------------------
    logger.info("⏳ [2/5] Generating steps from LLM...")
    
    gen = ollama_adapter.generate_and_format(
        prompt, 
        max_tokens=1500 if use_better_prompt else 1000,
        timeout=60 if use_better_prompt else 45
    )
    raw_text = gen.get("cleaned_text") or gen.get("raw_output") or ""

    if not raw_text:
        logger.error("Model returned empty response")
        return {"error": "Model returned empty response"}

    # Parse streaming JSON chunks from Ollama if present
    if isinstance(raw_text, str) and '{"model"' in raw_text and '"response"' in raw_text:
        log_fn = logger.debug if silent else logger.info
        log_fn("Detected Ollama streaming JSON format, parsing...")
        parsed_text = []
        
        # Try parsing line by line first
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
                if isinstance(chunk, dict) and "response" in chunk:
                    parsed_text.append(chunk.get("response", ""))
            except json.JSONDecodeError:
                pass
        
        # If that didn't work, try regex parsing for concatenated JSON
        if not parsed_text:
            for match in re.finditer(r'\{"model"[^}]+\}', raw_text):
                try:
                    chunk = json.loads(match.group())
                    if isinstance(chunk, dict) and "response" in chunk:
                        parsed_text.append(chunk.get("response", ""))
                except json.JSONDecodeError:
                    continue
        
        if parsed_text:
            raw_text = "".join(parsed_text).strip()
            log_fn = logger.debug if silent else logger.info
            log_fn(f"Parsed streaming response: {raw_text[:100]}...")
        else:
            logger.warning("Failed to parse streaming JSON, using raw text")

    # Try to parse JSON if better prompt was used
    orig_steps = []
    if use_better_prompt:
        try:
            # Look for JSON array pattern
            json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                orig_steps = json.loads(json_str)
                logger.info(f"✅ Successfully parsed JSON response with {len(orig_steps)} steps")
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse JSON, using text extraction: {e}")
    
    # Fallback to step extraction
    if not orig_steps:
        orig_steps = gen.get("steps") or ollama_adapter._extract_steps_from_text(raw_text)

    # --------------------------------------------------
    # 3️⃣ REWRITE AND CLEAN
    # --------------------------------------------------
    logger.info("⏳ [3/5] Rewriting and cleaning steps...")
    
    # Try FLAN rewrite if available
    try:
        if 'flan_rewrite' in globals() and callable(flan_rewrite):
            rewritten_steps = flan_rewrite(instr, orig_steps)
        else:
            raise ImportError("FLAN rewrite not available")
    except Exception:
        # Fallback to text extraction
        try:
            rewritten_steps = ollama_adapter._extract_steps_from_text(raw_text)
        except Exception:
            rewritten_steps = [
                {"step": i + 1, "action": line.strip(), "description": ""}
                for i, line in enumerate(raw_text.splitlines())
                if line.strip()
            ]
    
    # Clean up step numbering prefixes from actions
    for step in rewritten_steps:
        if isinstance(step, dict) and "action" in step:
            action = step.get("action", "").strip()
            # Remove leading numbers like "1. ", "2. ", etc.
            action = re.sub(r'^\d+\.\s*', '', action)
            step["action"] = action
            
            # Also clean description if present
            if "description" in step and step["description"]:
                desc = step.get("description", "").strip()
                desc = re.sub(r'^Step\s+\d+:\s*', '', desc, flags=re.IGNORECASE)
                desc = re.sub(r'^\d+\.\s*', '', desc)
                step["description"] = desc

    # --------------------------------------------------
    # 4️⃣ VALIDATION
    # --------------------------------------------------
    logger.info("⏳ [4/5] Validating step quality...")
    
    validator = StepQualityValidator()

    q_orig = validator.evaluate(orig_steps, instr)
    q_rew = validator.evaluate(rewritten_steps, instr)

    try:
        alg_orig = validator.validate_algorithm(instr, orig_steps)
    except Exception:
        alg_orig = {"is_valid": False, "confidence": 0.0}

    try:
        alg_rew = validator.validate_algorithm(instr, rewritten_steps)
    except Exception:
        alg_rew = {"is_valid": False, "confidence": 0.0}

    # --------------------------------------------------
    # 5️⃣ IMPERATIVE FIX (IF BOTH FAIL)
    # --------------------------------------------------
    if not alg_orig.get("is_valid", False) and not alg_rew.get("is_valid", False):
        log_fn = logger.debug if silent else logger.info
        log_fn("Both algorithmic validations failed. Applying imperative fix.")

        fixed = force_imperative(rewritten_steps)
        fixed_q = validator.evaluate(fixed, instr)
        fixed_alg = validator.validate_algorithm(instr, fixed)

        if fixed_alg.get("is_valid", False):
            rewritten_steps = fixed
            q_rew = fixed_q
            alg_rew = fixed_alg

    # --------------------------------------------------
    # 6️⃣ ABSTRACT STEPS
    # --------------------------------------------------
    try:
        abstract_steps = summarize_steps(rewritten_steps)
    except Exception:
        abstract_steps = []

    # --------------------------------------------------
    # 7️⃣ SELECT BEST VERSION
    # --------------------------------------------------
    logger.info("⏳ [5/5] Selecting best steps...")
    
    original_summary = {
        "steps": orig_steps,
        "quality": q_orig.get("quality_score", 0.0),
        "confidence": alg_orig.get("confidence", 0.0),
    }

    rewritten_summary = {
        "steps": rewritten_steps,
        "quality": q_rew.get("quality_score", 0.0),
        "confidence": alg_rew.get("confidence", 0.0),
    }

    try:
        chosen_steps, chosen_source = select_steps(original_summary, rewritten_summary)
    except Exception:
        chosen_steps, chosen_source = rewritten_steps, "rewritten"

    log_fn = logger.debug if silent else logger.info
    log_fn("Chosen steps source: %s", chosen_source)

    # --------------------------------------------------
    # 8️⃣ SAVE RESULTS (JSON)
    # --------------------------------------------------
    result = {
        "instruction": instr,
        "prompt_used": "enhanced" if use_better_prompt else "minimal",
        "generated": gen,
        "rewritten_text": raw_text,
        "rewritten_steps": rewritten_steps,
        "abstract_steps": abstract_steps,
        "chosen_steps": chosen_steps,
        "chosen_source": chosen_source,
        "validation": {
            "original_quality": q_orig,
            "rewritten_quality": q_rew,
            "original_algorithmic": alg_orig,
            "rewritten_algorithmic": alg_rew,
        },
        "timestamp": time.time(),
    }

    # Save full result history
    try:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if OUT_PATH.exists():
            with OUT_PATH.open("r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.append(result)
        with OUT_PATH.open("w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("Failed to save interactive results: %s", e)

    # --------------------------------------------------
    # 9️⃣ SAVE ESP32 EXECUTION FILE
    # --------------------------------------------------
    try:
        ESP32_OUT.parent.mkdir(parents=True, exist_ok=True)

        steps_for_esp = [
            {
                "step": s.get("step"),
                "action": s.get("action"),
                "description": s.get("description", "")
            }
            for s in chosen_steps
        ]

        compact = {
            "instruction": instr,
            "chosen": chosen_source,
            "steps": steps_for_esp,
            "timestamp": time.time(),
        }

        with ESP32_OUT.open("a", encoding="utf-8") as ef:
            ef.write(json.dumps(compact, ensure_ascii=False) + "\n")

    except Exception as e:
        logger.warning("Failed to write ESP32 JSONL: %s", e)

    # --------------------------------------------------
    # 🔟 UPDATE SELECTION REPORT
    # --------------------------------------------------
    try:
        report = {"total": 0, "rewritten_selected": 0, "original_selected": 0, "enhanced_prompt_used": 0}

        if SELECTION_REPORT.exists():
            with SELECTION_REPORT.open("r", encoding="utf-8") as rf:
                report = json.load(rf)

        report["total"] += 1
        
        if use_better_prompt:
            report["enhanced_prompt_used"] = report.get("enhanced_prompt_used", 0) + 1

        if chosen_source == "rewritten":
            report["rewritten_selected"] += 1
        else:
            report["original_selected"] += 1

        with SELECTION_REPORT.open("w", encoding="utf-8") as wf:
            json.dump(report, wf, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.warning("Failed to update selection report: %s", e)

    log_fn = logger.debug if silent else logger.info
    log_fn(
        "run_interactive completed | chosen=%s | total_steps=%d | prompt=%s",
        chosen_source,
        len(chosen_steps) if chosen_steps else 0,
        "enhanced" if use_better_prompt else "minimal"
    )

    # Print steps to console only when NOT in silent mode
    if not silent:
        print(f"\n{'='*60}")
        print(f"📋 Generated Steps for: '{instr}'")
        print(f"Source: {chosen_source} | Prompt: {'Enhanced' if use_better_prompt else 'Minimal'}")
        print(f"{'='*60}\n")
        
        if not chosen_steps:
            print("❌ No steps were generated")
        else:
            for i, step in enumerate(chosen_steps, 1):
                if isinstance(step, dict):
                    action = step.get("action", "").strip()
                    description = step.get("description", "").strip()
                    
                    # Clean up any remaining prefixes
                    action = re.sub(r'^\d+\.\s*', '', action)
                    action = re.sub(r'^Step\s+\d+:\s*', '', action, flags=re.IGNORECASE)
                    
                    # Show coordinates if available
                    coord_info = ""
                    if "x" in step and "y" in step:
                        coord_info = f" at ({step['x']}, {step['y']})"
                    
                    # Only show description if it adds value
                    if description and description != action:
                        # Clean description too
                        description = re.sub(r'^\d+\.\s*', '', description)
                        description = re.sub(r'^Step\s+\d+:\s*', '', description, flags=re.IGNORECASE)
                        
                        # Check if description is meaningfully different
                        if description.lower() != action.lower() and len(description) > len(action):
                            print(f"{i}. {action}{coord_info}")
                            print(f"   ➜ {description}")
                        else:
                            print(f"{i}. {action}{coord_info}")
                    else:
                        print(f"{i}. {action}{coord_info}")
                else:
                    step_str = str(step).strip()
                    step_str = re.sub(r'^\d+\.\s*', '', step_str)
                    print(f"{i}. {step_str}")
        
        print(f"\n{'='*60}")
        print(f"✅ Saved to: {OUT_PATH}")
        print(f"{'='*60}\n")

        if show_validation:
            print("\n📊 Validation Details:")
            print(json.dumps(result["validation"], indent=2))

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interactive generator with enhanced prompting")
    parser.add_argument("--show-validation", action="store_true", help="Print validation block after a run")
    parser.add_argument("--use-minimal-prompt", action="store_true", help="Use minimal prompt instead of enhanced")
    args = parser.parse_args()
    
    run_interactive(
        show_validation=args.show_validation,
        use_better_prompt=not args.use_minimal_prompt
    )






# import argparse
# import json
# import time
# import re
# from pathlib import Path
# from typing import Dict, Any, Optional

# from llm import ollama_adapter
# try:
#     from llm.flan_t5_rewriter import rewrite_steps as flan_rewrite
# except Exception:
#     from llm.simple_rewriter import rewrite_steps as flan_rewrite

# from llm.step_validators import StepQualityValidator
# from llm.hid_step_generator import generate_hid_steps_from_visual
# import logging

# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# OUT_PATH = Path("llm/interactive_results.json")
# ESP32_OUT = Path("llm/esp32_steps.jsonl")
# SELECTION_REPORT = Path("llm/selection_report.json")
# DISPLAY_OUT = Path("llm/esp32_display.jsonl")


# def summarize_steps(steps):
#     seen_move = False
#     out = []
#     for s in steps:
#         a = (s.get("action") or s.get("description") or "").strip() if isinstance(s, dict) else str(s).strip()
#         if not a:
#             continue
#         low = a.lower()
#         if ("new game" in low) or ("start" in low and "game" in low):
#             out.append({"step": len(out) + 1, "action": "Start", "description": "Create new game"})
#             continue
#         if any(k in low for k in ["left arrow", "right arrow", "up arrow", "down arrow", "press left", "press right", "press up", "press down", "arrow key", "arrow"]) or re.search(r"\b(move|slide)\b", low):
#             if not seen_move:
#                 seen_move = True
#                 out.append({"step": len(out) + 1, "action": "Move Tiles", "description": "Use arrow keys to move tiles toward merges"})
#             continue
#         if "merge" in low or "combine" in low:
#             out.append({"step": len(out) + 1, "action": "Merge Tiles", "description": "If two tiles of the same value touch, they merge into a higher-value tile"})
#             continue
#         if "rotate" in low or "clockwise" in low or "counterclockwise" in low:
#             out.append({"step": len(out) + 1, "action": "Rotate", "description": "Rotate tiles or change orientation if supported"})
#             continue
#         if "score" in low:
#             out.append({"step": len(out) + 1, "action": "Check Score", "description": "View current score on the game board"})
#             continue
#         if "restart" in low or "refresh" in low or "game over" in low:
#             out.append({"step": len(out) + 1, "action": "Game Over", "description": "If no merges remain the game ends; restart to play again"})
#             continue
#         first_clause = a.split(".")[0]
#         out.append({"step": len(out) + 1, "action": first_clause, "description": a})
#     return out


# def select_steps(original, rewritten):
#     tau = 0.55
#     orig_q = float(original.get("quality", 0.0))
#     rew_q = float(rewritten.get("quality", 0.0))
#     orig_conf = float(original.get("confidence", 0.0))
#     rew_conf = float(rewritten.get("confidence", 1.0))
#     if rew_q >= orig_q or rew_conf >= tau:
#         return rewritten.get("steps", []), "rewritten"
#     if orig_conf >= tau:
#         return original.get("steps", []), "original"
#     return rewritten.get("steps", []), "rewritten"


# def force_imperative(steps):
#     """Heuristic fixer: ensure each step `action` starts with a verb.
#     This is a lightweight fallback when the validator fails.
#     """
#     verb_map = {
#         "open": ["open", "navigate", "go to", "visit", "launch"],
#         "click": ["click", "tap", "press", "select", "initiate"],
#         "upload": ["upload", "choose file", "select file", "pick"],
#         "save": ["save", "confirm", "apply"],
#         "wait": ["wait", "loading", "uploading"],
#         "enter": ["enter", "input", "type", "fill"],
#         "verify": ["verify", "check", "validate", "ensure"],
#     }

#     def pick_verb(text):
#         low = text.lower()
#         for v, kws in verb_map.items():
#             for kw in kws:
#                 if kw in low:
#                     return v.capitalize()
#         # Check if it already starts with a verb
#         if re.match(r'^(open|click|enter|type|verify|check|select|navigate|launch|tap|press|input|fill|validate)\b', low):
#             return None  # Already has a verb
#         return "Click"

#     fixed = []
#     for i, s in enumerate(steps):
#         if isinstance(s, dict):
#             act = (s.get("action") or "").strip()
#             desc = (s.get("description") or "").strip()
            
#             # Clean numbering prefixes
#             act = re.sub(r'^\d+\.\s*', '', act)
#             act = re.sub(r'^Step\s+\d+:\s*', '', act, flags=re.IGNORECASE)
            
#             if re.match(r"^[A-Za-z]+\b", act):
#                 # Check if it already starts with a verb
#                 verb = pick_verb(act)
#                 if verb:
#                     new_act = f"{verb} {act}"
#                 else:
#                     new_act = act
#             else:
#                 verb = pick_verb(act or desc)
#                 new_act = f"{verb} {act}" if act else f"{verb}"
            
#             fixed.append({"step": s.get("step", i + 1), "action": new_act, "description": desc})
#         else:
#             text = str(s).strip()
#             text = re.sub(r'^\d+\.\s*', '', text)
#             verb = pick_verb(text)
#             new_act = f"{verb} {text}" if (verb and text) else text
#             fixed.append({"step": i + 1, "action": new_act, "description": ""})
#     return fixed


# def run_interactive(
#     instruction: str | None = None, 
#     show_validation: bool = False, 
#     silent: bool = False,
#     visual_data: Optional[Dict[str, Any]] = None,
#     skip_validation: bool = False
# ):
#     """
#     Run interactive step generation.
    
#     Args:
#         instruction: User instruction text
#         show_validation: Show validation details
#         silent: Suppress console output
#         visual_data: Optional visual perception data for HID generation
#         skip_validation: Skip visual validation check
        
#     Returns:
#         If visual_data provided: HID commands with validation
#         If no visual_data: Abstract steps (original behavior)
#     """
    
#     # ============================================================
#     # NEW: VISUAL-AWARE HID GENERATION MODE
#     # ============================================================
#     if visual_data is not None:
#         logger.info("🎯 Visual-aware HID generation mode enabled")
        
#         if instruction is None:
#             instruction = input("Enter instruction: ")
        
#         if not instruction or not instruction.strip():
#             logger.warning("No instruction provided")
#             return {"error": "No instruction provided"}
        
#         logger.info(f"⏳ Generating HID commands for: {instruction[:60]}...")
        
#         # Use HID generation pipeline with validation
#         result = generate_hid_steps_from_visual(
#             instruction=instruction,
#             visual_data=visual_data,
#             model="mistral",
#             skip_validation=skip_validation
#         )
        
#         # Check if validation failed
#         if result.get("status") == "validation_failed":
#             logger.warning("⚠️ Validation failed - elements not found on screen")
#             logger.info(f"   Missing: {result.get('validation', {}).get('missing_elements', [])}")
#             logger.info(f"   Suggested: {result.get('suggested_actions', [])}")
#         else:
#             logger.info(f"✅ Generated {result.get('total_commands', 0)} HID commands")
        
#         return result
    
#     # ============================================================
#     # ORIGINAL: ABSTRACT STEP GENERATION MODE (NO VISUAL DATA)
#     # ============================================================
#     if instruction is None:
#         instr = input("Enter instruction: ")
#     else:
#         instr = instruction

#     if not instr or not instr.strip():
#         logger.warning("No instruction provided")
#         return {"error": "No instruction provided"}

#     # Always show progress, even in silent mode
#     logger.info("⏳ [1/5] Preparing prompt for: %s", instr[:50] + "..." if len(instr) > 50 else instr)

#     # --------------------------------------------------
#     # 1️⃣ MINIMAL PROMPT FOR MAXIMUM SPEED
#     # --------------------------------------------------
#     strict_prompt = f"""Task: "{instr}"

# Write SHORT steps (one line each, no sub-points):
# 1. Open page
# 2. Enter username
# 3. Enter password
# 4. Click login
# 5. Verify success

# Your steps:"""

#     # --------------------------------------------------
#     # 2️⃣ GENERATE (OLLAMA)
#     # --------------------------------------------------
#     logger.info("⏳ [2/5] Generating steps from LLM (max 30s timeout, 100 tokens)...")
    
#     gen = ollama_adapter.generate_and_format(strict_prompt, max_tokens=100, timeout=30)
#     raw_text = gen.get("cleaned_text") or gen.get("raw_output") or ""

#     if not raw_text:
#         logger.error("Model returned empty response")
#         return {"error": "Model returned empty response"}

#     # Parse streaming JSON chunks from Ollama if present
#     if isinstance(raw_text, str) and '{"model"' in raw_text and '"response"' in raw_text:
#         log_fn = logger.debug if silent else logger.info
#         log_fn("Detected Ollama streaming JSON format, parsing...")
#         parsed_text = []
        
#         # Try parsing line by line first
#         for line in raw_text.splitlines():
#             line = line.strip()
#             if not line:
#                 continue
#             try:
#                 chunk = json.loads(line)
#                 if isinstance(chunk, dict) and "response" in chunk:
#                     parsed_text.append(chunk.get("response", ""))
#             except json.JSONDecodeError:
#                 pass
        
#         # If that didn't work, try regex parsing for concatenated JSON
#         if not parsed_text:
#             for match in re.finditer(r'\{"model"[^}]+\}', raw_text):
#                 try:
#                     chunk = json.loads(match.group())
#                     if isinstance(chunk, dict) and "response" in chunk:
#                         parsed_text.append(chunk.get("response", ""))
#                 except json.JSONDecodeError:
#                     continue
        
#         if parsed_text:
#             raw_text = "".join(parsed_text).strip()
#             log_fn = logger.debug if silent else logger.info
#             log_fn(f"Parsed streaming response: {raw_text[:100]}...")
#         else:
#             logger.warning("Failed to parse streaming JSON, using raw text")

#     orig_steps = gen.get("steps") or []

#     # --------------------------------------------------
#     # 3️⃣ REWRITE (FLAN / FALLBACK)
#     # --------------------------------------------------
#     logger.info("⏳ [3/5] Rewriting and cleaning steps...")
    
#     rewritten_text = raw_text

#     try:
#         rewritten_steps = ollama_adapter._extract_steps_from_text(rewritten_text)
#     except Exception:
#         rewritten_steps = [
#             {"step": i + 1, "action": line.strip(), "description": ""}
#             for i, line in enumerate(rewritten_text.splitlines())
#             if line.strip()
#         ]
    
#     # Clean up step numbering prefixes from actions
#     for step in rewritten_steps:
#         if isinstance(step, dict) and "action" in step:
#             action = step.get("action", "").strip()
#             # Remove leading numbers like "1. ", "2. ", etc.
#             action = re.sub(r'^\d+\.\s*', '', action)
#             step["action"] = action
            
#             # Also clean description if present
#             if "description" in step and step["description"]:
#                 desc = step.get("description", "").strip()
#                 desc = re.sub(r'^Step\s+\d+:\s*', '', desc, flags=re.IGNORECASE)
#                 desc = re.sub(r'^\d+\.\s*', '', desc)
#                 step["description"] = desc

#     # --------------------------------------------------
#     # 4️⃣ VALIDATION
#     # --------------------------------------------------
#     logger.info("⏳ [4/5] Validating step quality...")
    
#     validator = StepQualityValidator()

#     q_orig = validator.evaluate(orig_steps, instr)
#     q_rew = validator.evaluate(rewritten_steps, instr)

#     try:
#         alg_orig = validator.validate_algorithm(instr, orig_steps)
#     except Exception:
#         alg_orig = {"is_valid": False, "confidence": 0.0}

#     try:
#         alg_rew = validator.validate_algorithm(instr, rewritten_steps)
#     except Exception:
#         alg_rew = {"is_valid": False, "confidence": 0.0}

#     # --------------------------------------------------
#     # 5️⃣ IMPERATIVE FIX (IF BOTH FAIL)
#     # --------------------------------------------------
#     if not alg_orig.get("is_valid", False) and not alg_rew.get("is_valid", False):
#         log_fn = logger.debug if silent else logger.info
#         log_fn("Both algorithmic validations failed. Applying imperative fix.")

#         fixed = force_imperative(rewritten_steps)
#         fixed_q = validator.evaluate(fixed, instr)
#         fixed_alg = validator.validate_algorithm(instr, fixed)

#         if fixed_alg.get("is_valid", False):
#             rewritten_steps = fixed
#             q_rew = fixed_q
#             alg_rew = fixed_alg

#     # --------------------------------------------------
#     # 6️⃣ ABSTRACT STEPS
#     # --------------------------------------------------
#     try:
#         abstract_steps = summarize_steps(rewritten_steps)
#     except Exception:
#         abstract_steps = []

#     # --------------------------------------------------
#     # 7️⃣ SELECT BEST VERSION
#     # --------------------------------------------------
#     logger.info("⏳ [5/5] Selecting best steps...")
    
#     original_summary = {
#         "steps": orig_steps,
#         "quality": q_orig.get("quality_score", 0.0),
#         "confidence": alg_orig.get("confidence", 0.0),
#     }

#     rewritten_summary = {
#         "steps": rewritten_steps,
#         "quality": q_rew.get("quality_score", 0.0),
#         "confidence": alg_rew.get("confidence", 0.0),
#     }

#     try:
#         chosen_steps, chosen_source = select_steps(original_summary, rewritten_summary)
#     except Exception:
#         chosen_steps, chosen_source = rewritten_steps, "rewritten"

#     log_fn = logger.debug if silent else logger.info
#     log_fn("Chosen steps source: %s", chosen_source)

#     # --------------------------------------------------
#     # 8️⃣ SAVE RESULTS (JSON)
#     # --------------------------------------------------
#     result = {
#         "instruction": instr,
#         "generated": gen,
#         "rewritten_text": rewritten_text,
#         "rewritten_steps": rewritten_steps,
#         "abstract_steps": abstract_steps,
#         "chosen_steps": chosen_steps,
#         "chosen_source": chosen_source,
#         "validation": {
#             "original_quality": q_orig,
#             "rewritten_quality": q_rew,
#             "original_algorithmic": alg_orig,
#             "rewritten_algorithmic": alg_rew,
#         },
#         "timestamp": time.time(),
#     }

#     # Save full result history
#     try:
#         OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
#         existing = []
#         if OUT_PATH.exists():
#             with OUT_PATH.open("r", encoding="utf-8") as f:
#                 existing = json.load(f)
#         existing.append(result)
#         with OUT_PATH.open("w", encoding="utf-8") as f:
#             json.dump(existing, f, indent=2, ensure_ascii=False)
#     except Exception as e:
#         logger.warning("Failed to save interactive results: %s", e)

#     # --------------------------------------------------
#     # 9️⃣ SAVE ESP32 EXECUTION FILE
#     # --------------------------------------------------
#     try:
#         ESP32_OUT.parent.mkdir(parents=True, exist_ok=True)

#         steps_for_esp = [
#             {
#                 "step": s.get("step"),
#                 "action": s.get("action"),
#                 "description": s.get("description", "")
#             }
#             for s in chosen_steps
#         ]

#         compact = {
#             "instruction": instr,
#             "chosen": chosen_source,
#             "steps": steps_for_esp,
#             "timestamp": time.time(),
#         }

#         with ESP32_OUT.open("a", encoding="utf-8") as ef:
#             ef.write(json.dumps(compact, ensure_ascii=False) + "\n")

#     except Exception as e:
#         logger.warning("Failed to write ESP32 JSONL: %s", e)

#     # --------------------------------------------------
#     # 🔟 UPDATE SELECTION REPORT
#     # --------------------------------------------------
#     try:
#         report = {"total": 0, "rewritten_selected": 0, "original_selected": 0}

#         if SELECTION_REPORT.exists():
#             with SELECTION_REPORT.open("r", encoding="utf-8") as rf:
#                 report = json.load(rf)

#         report["total"] += 1

#         if chosen_source == "rewritten":
#             report["rewritten_selected"] += 1
#         else:
#             report["original_selected"] += 1

#         with SELECTION_REPORT.open("w", encoding="utf-8") as wf:
#             json.dump(report, wf, indent=2, ensure_ascii=False)

#     except Exception as e:
#         logger.warning("Failed to update selection report: %s", e)

#     log_fn = logger.debug if silent else logger.info
#     log_fn(
#         "run_interactive completed | chosen=%s | total_steps=%d",
#         chosen_source,
#         len(chosen_steps) if chosen_steps else 0,
#     )

#     # Print steps to console only when NOT in silent mode
#     if not silent:
#         print(f"\n{'='*60}")
#         print(f"📋 Generated Steps for: '{instr}'")
#         print(f"Source: {chosen_source}")
#         print(f"{'='*60}\n")
        
#         if not chosen_steps:
#             print("❌ No steps were generated")
#         else:
#             for i, step in enumerate(chosen_steps, 1):
#                 if isinstance(step, dict):
#                     action = step.get("action", "").strip()
#                     description = step.get("description", "").strip()
                    
#                     # Clean up any remaining prefixes
#                     action = re.sub(r'^\d+\.\s*', '', action)
#                     action = re.sub(r'^Step\s+\d+:\s*', '', action, flags=re.IGNORECASE)
                    
#                     # Only show description if it adds value
#                     if description and description != action:
#                         # Clean description too
#                         description = re.sub(r'^\d+\.\s*', '', description)
#                         description = re.sub(r'^Step\s+\d+:\s*', '', description, flags=re.IGNORECASE)
                        
#                         # Check if description is meaningfully different
#                         if description.lower() != action.lower() and len(description) > len(action):
#                             print(f"{i}. {action}")
#                             print(f"   ➜ {description}")
#                         else:
#                             print(f"{i}. {action}")
#                     else:
#                         print(f"{i}. {action}")
#                 else:
#                     step_str = str(step).strip()
#                     step_str = re.sub(r'^\d+\.\s*', '', step_str)
#                     print(f"{i}. {step_str}")
        
#         print(f"\n{'='*60}")
#         print(f"✅ Saved to: {OUT_PATH}")
#         print(f"{'='*60}\n")

#         if show_validation:
#             print("\n📊 Validation Details:")
#             print(json.dumps(result["validation"], indent=2))

#     return result



# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Interactive generator with optional validation display")
#     parser.add_argument("--show-validation", action="store_true", help="Print validation block after a run")
#     args = parser.parse_args()
#     run_interactive(show_validation=args.show_validation)