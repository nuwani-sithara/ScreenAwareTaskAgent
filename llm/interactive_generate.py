import argparse
import json
import time
import re
from pathlib import Path

from llm import ollama_adapter
try:
    from llm.flan_t5_rewriter import rewrite_steps as flan_rewrite
except Exception:
    from llm.simple_rewriter import rewrite_steps as flan_rewrite

from llm.step_validators import StepQualityValidator
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


def remove_duplicate_steps(steps):
    """Remove duplicate steps based on action similarity.
    
    Keeps the first occurrence of each unique action.
    Uses normalized text comparison to catch near-duplicates.
    """
    if not steps:
        return steps
    
    seen_actions = set()
    unique_steps = []
    
    for step in steps:
        if isinstance(step, dict):
            action = step.get("action", "").strip().lower()
            description = step.get("description", "").strip().lower()
            # Use both action and description for better duplicate detection
            key = f"{action}|{description}"
        else:
            key = str(step).strip().lower()
        
        # Normalize: remove extra spaces, punctuation
        normalized = re.sub(r'[^\w\s|]', '', key)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        if normalized and normalized not in seen_actions:
            seen_actions.add(normalized)
            unique_steps.append(step)
    
    # Renumber steps sequentially starting from 1
    renumbered_steps = []
    for i, step in enumerate(unique_steps, 1):
        if isinstance(step, dict):
            new_step = step.copy()
            new_step["step"] = i
            renumbered_steps.append(new_step)
        else:
            renumbered_steps.append(step)
    
    return renumbered_steps


def force_imperative(steps):
    """Heuristic fixer: ensure each step `action` starts with a verb.
    This is a lightweight fallback when the validator fails.
    """
    verb_map = {
        "open": ["open", "navigate", "go to", "visit"],
        "click": ["click", "tap", "press", "select"],
        "upload": ["upload", "choose file", "select file", "pick"],
        "save": ["save", "confirm", "apply"],
        "wait": ["wait", "loading", "uploading"],
    }

    def pick_verb(text):
        low = text.lower()
        for v, kws in verb_map.items():
            for kw in kws:
                if kw in low:
                    return v.capitalize()
        return "Click"

    fixed = []
    for i, s in enumerate(steps):
        if isinstance(s, dict):
            act = (s.get("action") or "").strip()
            if re.match(r"^[A-Za-z]+\b", act):
                # starts with a word; assume ok
                new_act = act
            else:
                verb = pick_verb(act or s.get("description", ""))
                new_act = f"{verb} {act}" if act else f"{verb}"
            fixed.append({"step": s.get("step", i + 1), "action": new_act, "description": s.get("description", "")})
        else:
            text = str(s).strip()
            verb = pick_verb(text)
            new_act = f"{verb} {text}" if text else verb
            fixed.append({"step": i + 1, "action": new_act, "description": ""})
    return fixed


def run_interactive(instruction: str | None = None, show_validation: bool = False):
    if instruction is None:
        instr = input("Enter instruction: ")
    else:
        instr = instruction

    if not instr.strip():
        logger.warning("No instruction provided")
        return

    logger.info("Starting interactive run for instruction: %s", instr)

    strict_prompt = (
        f"You are an expert UI automation agent. Given the instruction: '{instr}', "
        "return a concise, numbered list of UNIQUE UI steps to accomplish the task. "
        "Each step should start with a strong action verb and be DIFFERENT from other steps. "
        "DO NOT repeat the same action twice.\n"
        "Example:\n1. Open the app\n2. Click 'Add to Cart'\n3. Confirm purchase\n\nSteps:"
    )

    logger.info("Generating steps with Ollama...")
    gen = ollama_adapter.generate_and_format(strict_prompt)
    raw_text = gen.get("cleaned_text") or gen.get("raw_output") or ""
    error_msg = gen.get("error") or ""
    if not error_msg and isinstance(raw_text, str) and (
        "Ollama run failed" in raw_text or "returned non-zero exit status" in raw_text
    ):
        error_msg = raw_text.strip()

    if error_msg:
        logger.error("Ollama generation failed; not saving steps.")
        logger.error("Error message: %s", error_msg)
        logger.debug("Raw Ollama output: %s", raw_text)
        return

    # Attempt to parse JSON chunks from output
    responses = []
    try:
        for m in re.finditer(r"\{.*?\}\s*", raw_text, re.S):
            chunk = m.group()
            try:
                obj = json.loads(chunk)
                if isinstance(obj, dict) and 'response' in obj:
                    responses.append(obj.get('response') or '')
            except Exception:
                continue
    except Exception:
        responses = []

    if responses:
        cleaned = ''.join(responses).strip()
        orig_steps = ollama_adapter._extract_steps_from_text(cleaned)
        logger.info("Extracted %d original steps from JSON responses", len(orig_steps))
    else:
        orig_steps = gen.get("steps") or []
        logger.info("Extracted %d original steps from raw text", len(orig_steps))

    logger.info("Rewriting steps with Flan‑T5 (or fallback)...")
    rewritten_text = flan_rewrite(raw_text) if callable(flan_rewrite) else raw_text

    try:
        rewritten_steps = ollama_adapter._extract_steps_from_text(rewritten_text)
        logger.info("Extracted %d rewritten steps", len(rewritten_steps))
    except Exception:
        rewritten_steps = [
            {"step": i + 1, "action": s.strip(), "description": f"Step {i+1}: {s.strip()}"}
            for i, s in enumerate([l for l in rewritten_text.splitlines() if l.strip()])
        ]
        logger.warning("Fallback extraction used; %d steps created", len(rewritten_steps))

    validator = StepQualityValidator()

    q_orig = validator.evaluate(orig_steps, instr)
    q_rew = validator.evaluate(rewritten_steps, instr)

    logger.info("Original steps quality: %s", q_orig)
    logger.info("Rewritten steps quality: %s", q_rew)

    try:
        alg_orig = validator.validate_algorithm(instr, orig_steps)
    except Exception:
        alg_orig = {"confidence": 0.0}
        logger.warning("Original algorithmic validation failed")

    try:
        alg_rew = validator.validate_algorithm(instr, rewritten_steps)
    except Exception:
        alg_rew = {"confidence": 0.0}
        logger.warning("Rewritten algorithmic validation failed")

    try:
        abstract_steps = summarize_steps(rewritten_steps)
        logger.info("Abstracted %d steps", len(abstract_steps))
    except Exception:
        abstract_steps = []
        logger.warning("Failed to summarize steps")

    # Attempt imperative fix if both validators fail
    try:
        if (not alg_orig.get("is_valid", False)) and (not alg_rew.get("is_valid", False)):
            logger.info("Both algorithmic validators failed; attempting imperative fix")
            fixed = force_imperative(rewritten_steps)
            fixed_q = validator.evaluate(fixed, instr)
            fixed_alg = validator.validate_algorithm(instr, fixed)
            if fixed_alg.get("is_valid", False):
                rewritten_steps = fixed
                logger.info("Imperative fix applied successfully | Confidence: %s", fixed_alg.get("confidence", 0.0))
                result = {
                    "rewritten_steps": rewritten_steps,
                    "validation": {
                        "rewritten_quality": fixed_q,
                        "rewritten_algorithmic": fixed_alg
                    }
                }
    except Exception:
        logger.exception("Imperative fix attempt failed")

    result = {
        "instruction": instr,
        "generated": gen,
        "rewritten_text": rewritten_text,
        "rewritten_steps": rewritten_steps,
        "abstract_steps": abstract_steps,
        "validation": {
            "original_quality": q_orig,
            "rewritten_quality": q_rew,
            "original_algorithmic": alg_orig,
            "rewritten_algorithmic": alg_rew
        },
        "timestamp": time.time(),
    }

    logger.info("run_interactive completed | Total steps: %d", len(rewritten_steps))
    # Sanitize validation details to avoid exposing internal boolean flags like hasVerb
    def _sanitize_validation(res):
        try:
            val = res.get("validation", {})
            for k in ("original_algorithmic", "rewritten_algorithmic"):
                alg = val.get(k, {})
                if isinstance(alg, dict) and "details" in alg and isinstance(alg["details"], list):
                    cleaned = []
                    for d in alg["details"]:
                        if isinstance(d, str):
                            # remove occurrences like "hasVerb=True," or "hasVerb=False," or "hasVerb=True"
                            cd = re.sub(r"\bhasVerb=(?:True|False),?\s*", "", d)
                            cleaned.append(cd)
                        else:
                            cleaned.append(d)
                    alg["details"] = cleaned
            res["validation"] = val
        except Exception:
            pass

    _sanitize_validation(result)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if OUT_PATH.exists():
        try:
            with OUT_PATH.open("r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []
    existing.append(result)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    original_summary = {"steps": orig_steps, "quality": q_orig.get("quality_score", 0.0), "confidence": alg_orig.get("confidence", 0.0)}
    rewritten_summary = {"steps": rewritten_steps, "quality": q_rew.get("quality_score", 0.0), "confidence": alg_rew.get("confidence", 0.0)}
    try:
        display_steps, display_source = select_steps(original_summary, rewritten_summary)
        # If rewritten steps look like model metadata, force fallback to original
        if display_source == "rewritten" and display_steps and any(
            isinstance(s, dict) and ("model" in s.get("action", "") or "created_at" in s.get("action", ""))
            for s in display_steps):
            display_steps, display_source = original_summary["steps"], "original-forced"
        
        # Remove duplicate steps
        original_count = len(display_steps)
        display_steps = remove_duplicate_steps(display_steps)
        if len(display_steps) < original_count:
            removed_count = original_count - len(display_steps)
            print(f"🔍 Removed {removed_count} duplicate step(s)")
    except Exception:
        display_steps, display_source = rewritten_steps, "rewritten"
    
    # Debug: Log step count before printing
    logger.info(f"Displaying {len(display_steps)} steps (source: {display_source})")
    
    print(f"\n--- Chosen Steps ({display_source}) ---")
    if not display_steps:
        print("(No steps extracted)")
    else:
        for i, s in enumerate(display_steps, 1):
            if isinstance(s, dict):
                action = s.get("action", "").strip()
                description = s.get("description", "").strip()
                
                # Clean up action: remove leading numbers and "Step X:" prefixes
                action = re.sub(r'^\d+\.\s*', '', action)  # Remove "1. " prefix
                action = re.sub(r'^Step\s+\d+:\s*', '', action, flags=re.IGNORECASE)  # Remove "Step 1:" prefix
                
                # Only show description if it's meaningfully different from action
                # Clean description similarly
                clean_desc = re.sub(r'^\d+\.\s*', '', description)
                clean_desc = re.sub(r'^Step\s+\d+:\s*', '', clean_desc, flags=re.IGNORECASE)
                
                # Check if description adds value
                if clean_desc and clean_desc.lower() != action.lower() and len(clean_desc) > len(action) + 10:
                    print(f"{i}. {action}")
                    print(f"   → {clean_desc}")
                else:
                    print(f"{i}. {action}")
            else:
                step_text = str(s).strip()
                step_text = re.sub(r'^\d+\.\s*', '', step_text)
                print(f"{i}. {step_text}")
    print(f"\nSaved result to {OUT_PATH}")
    try:
        ESP32_OUT.parent.mkdir(parents=True, exist_ok=True)
        with ESP32_OUT.open("a", encoding="utf-8") as ef:
            # include description when available to preserve executor context
            if display_steps and isinstance(display_steps[0], dict):
                steps_for_esp = [{"step": s.get("step"), "action": s.get("action"), "description": s.get("description", "")} for s in display_steps]
            else:
                steps_for_esp = [{"step": i + 1, "action": str(s), "description": ""} for i, s in enumerate(display_steps)]

            compact = {
                "instruction": instr,
                "chosen": display_source,
                "steps": steps_for_esp,
                "timestamp": time.time(),
            }
            line = json.dumps(compact, ensure_ascii=False)
            ef.write(line + "\n")
            # Send steps to agentic AI backend (optional - backend must be running)
            try:
                import requests
                print("📤 Sending steps to backend & waiting for execution...")
                # Increased timeout since backend executes the full agentic loop (vision + planning + HID)
                # Backend planning calls Ollama LLM which can take 60-120s, plus vision/execution overhead
                resp = requests.post("http://localhost:8000/llm/steps", json=compact, timeout=300)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("status") == "executed":
                        print(f"✅ Steps sent & executed by agentic AI backend!")
                        exec_result = result.get("execution_result", {})
                        exec_success = exec_result.get("evaluation", {}).get("success", False)
                        print(f"   Execution success: {exec_success}")
                    else:
                        print(f"✅ Sent steps to agentic AI backend: {resp.status_code}")
                else:
                    print(f"⚠️  Backend responded with status: {resp.status_code}")
            except requests.exceptions.ConnectionError:
                print("⚠️  Backend not running at localhost:8000 - steps saved locally only")
            except requests.exceptions.Timeout:
                print("⚠️  Backend execution timed out (>300s) - steps were sent but execution may still be running")
            except Exception as e:
                print(f"⚠️  Failed to send steps to backend: {type(e).__name__}")
        print(f"Appended chosen steps to {ESP32_OUT}")
        # Also write a human-readable display JSONL line for quick review on host
        try:
            display_lines = [f"{s.get('step')} {s.get('action')}: {s.get('description','').strip()}" for s in steps_for_esp]
            disp_obj = {"instruction": instr, "chosen": display_source, "display": display_lines, "timestamp": time.time()}
            DISPLAY_OUT.parent.mkdir(parents=True, exist_ok=True)
            with DISPLAY_OUT.open("a", encoding="utf-8") as df:
                df.write(json.dumps(disp_obj, ensure_ascii=False) + "\n")
            print(f"Appended human-readable display to {DISPLAY_OUT}")
        except Exception as e:
            print("Failed to write display JSONL:", e)
    except Exception as e:
        print("Failed to write ESP32 JSONL:", e)
    try:
        report = {"total": 0, "rewritten_selected": 0, "original_selected": 0, "forced_rewritten": 0}
        if SELECTION_REPORT.exists():
            try:
                with SELECTION_REPORT.open("r", encoding="utf-8") as rf:
                    report = json.load(rf)
            except Exception:
                report = {"total": 0, "rewritten_selected": 0, "original_selected": 0, "forced_rewritten": 0}
        report["total"] = report.get("total", 0) + 1
        if display_source == "rewritten":
            report["rewritten_selected"] = report.get("rewritten_selected", 0) + 1
        else:
            report["original_selected"] = report.get("original_selected", 0) + 1
        with SELECTION_REPORT.open("w", encoding="utf-8") as wf:
            json.dump(report, wf, indent=2, ensure_ascii=False)
        print(f"Updated selection report: {SELECTION_REPORT}")
        if show_validation:
            try:
                print("Validation:")
                print(json.dumps(result.get("validation", {}), indent=2, ensure_ascii=False))
            except Exception as e:
                print("Failed to print validation:", e)
    except Exception as e:
        print("Failed to update selection report:", e)
    
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interactive generator with optional validation display")
    parser.add_argument("--show-validation", action="store_true", help="Print validation block after a run")
    args = parser.parse_args()
    run_interactive(show_validation=args.show_validation)