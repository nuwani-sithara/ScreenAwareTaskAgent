"""Adapter to call Ollama and format outputs into the project's step schema.

This file avoids importing `llm.demo` to keep it lightweight.
It provides `generate_and_format(instruction, model)` which returns a dict:
    {
      'instruction': instruction,
      'category': category,
      'steps': [ {step, action, description}, ... ],
      'total_steps': N,
      'status': 'ready_for_execution' | 'needs_review',
      'raw_output': <text>,
      'timestamp': <iso>
    }

The step extraction logic is a small copy of the extractor used in `llm/demo.py`.
"""
from datetime import datetime
import json
import re
from typing import List, Dict

from .ollama_client import OllamaClient


def _extract_steps_from_text(output_text: str) -> List[Dict]:
    steps = []
    text = (output_text or "").strip()
    if not text:
        return []

    # 1) Try explicit 'Step N:' patterns
    step_matches = re.findall(r"Step\s*(\d+)\s*[:\.]\s*(.*?)(?=\s*Step\s*\d+\s*[:\.]|$)", text, re.IGNORECASE | re.DOTALL)
    for step_num, action in step_matches:
        try:
            step_num = int(step_num)
            action = action.strip()
            if action:
                steps.append({"step": step_num, "action": action, "description": f"Step {step_num}: {action}"})
        except Exception:
            continue

    # 2) Try numbered lists like '1. Do X' or '2) Do Y'
    if not steps:
        numbered = re.findall(r"(?m)^\s*(\d+)[\.)]\s*(.*?)(?=^\s*\d+[\.)]\s*|\Z)", text, re.S)
        if numbered:
            for num, action in numbered:
                try:
                    n = int(num)
                    a = action.strip()
                    if a:
                        steps.append({"step": n, "action": a, "description": f"Step {n}: {a}"})
                except Exception:
                    continue
    
    # 2b) Try inline numbered steps (e.g., "Do X 2. Do Y 3. Do Z")
    if not steps:
        # Match patterns like "text 2. more text 3. even more" where numbers appear mid-string
        inline_pattern = r"(?:^|(?<=\d\.)\s*)([^\.]+?)(?:\s+(\d+)\.|$)"
        parts = re.split(r'\s+(\d+)\.', text)
        if len(parts) > 2:  # Has inline numbering
            temp_steps = []
            i = 0
            while i < len(parts):
                if i == 0 and parts[i].strip():
                    # First part before any number
                    temp_steps.append((1, parts[i].strip()))
                    i += 1
                elif i + 1 < len(parts) and parts[i].isdigit():
                    # Found a number followed by text
                    num = int(parts[i])
                    action = parts[i + 1].strip()
                    if action:
                        temp_steps.append((num, action))
                    i += 2
                else:
                    i += 1
            if temp_steps:
                for n, a in temp_steps:
                    steps.append({"step": n, "action": a, "description": f"Step {n}: {a}"})


    # 3) Bullet lists
    if not steps:
        bullets = re.findall(r"(?m)^\s*[-•*]\s*(.+)$", text)
        if bullets:
            for i, b in enumerate(bullets, 1):
                b = b.strip()
                if b:
                    steps.append({"step": i, "action": b, "description": f"Step {i}: {b}"})

    # 4) Fallback: split into sentences and keep up to 10
    if not steps:
        sentences = [s.strip() for s in re.split(r'[\n\.]+', text) if s.strip()]
        for i, sentence in enumerate(sentences[:10], 1):
            if sentence and len(sentence) > 3:
                steps.append({"step": i, "action": sentence, "description": f"Step {i}: {sentence}"})

    # 5) As a last resort, single-step with trimmed text
    if not steps and text:
        steps = [{"step": 1, "action": text[:300], "description": text[:300]}]

    # Ensure ordered and unique by step id
    unique = {s["step"]: s for s in steps}
    ordered = [unique[k] for k in sorted(unique.keys())]
    return ordered


def generate_and_format(instruction: str, model: str = "mistral", client: OllamaClient = None, max_tokens: int = 100, timeout: int = 30) -> Dict:
    """Generate using Ollama and format to project schema.

    Returns a dict suitable for saving into pretty JSON logs.
    """
    cat = "general_software"
    if any(w in instruction.lower() for w in ["2048", "swipe", "game", "play"]):
        cat = "game_2048"

    client = client or OllamaClient()
    raw = client.generate(instruction, model=model, max_tokens=max_tokens, timeout=timeout)
    steps = _extract_steps_from_text(raw)

    result = {
        "instruction": instruction,
        "category": cat,
        "steps": steps,
        "total_steps": len(steps),
        "status": "ready_for_execution" if len(steps) > 0 else "needs_review",
        "raw_output": raw,
        "timestamp": datetime.utcnow().isoformat()
    }

    return result


if __name__ == '__main__':
    c = OllamaClient()
    print(generate_and_format('Play 2048 game: restart game', model='mistral', client=c))
