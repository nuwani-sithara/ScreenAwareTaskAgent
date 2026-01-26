import json
import time
from pathlib import Path
from typing import Dict, Any

try:
    from llm_n.flan_t5_rewriter import rewrite_steps
except Exception:
    from llm_n.simple_rewriter import rewrite_steps

try:
    from llm_n.ollama_adapter import _extract_steps_from_text
except Exception:
    _extract_steps_from_text = None

from llm.step_validators import StepQualityValidator, validate_steps_hsv_a


def _extract_steps_fallback(text: str):
    # simple fallback: split on numbered lines or bullets
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    steps = []
    for l in lines:
        if l[0].isdigit() and (l[1:2] in ".) "):
            # '1.' or '1)' style
            parts = l.split(None, 1)
            steps.append(parts[1] if len(parts) > 1 else l)
        elif l.startswith("-") or l.startswith("*"):
            steps.append(l[1:].strip())
        else:
            # treat as sentence if short
            steps.append(l)
    return steps


def process_entries(input_path: str = "llm_n/generated_ollama_pretty.jsonl",
                    output_path: str = "llm_n/hybrid_results_pretty.jsonl",
                    model_name: str = "google/flan-t5-small") -> Dict[str, int]:
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = {"total": 0, "rewrites_better": 0}
    import re
    with inp.open("r", encoding="utf-8") as fr, out.open("w", encoding="utf-8") as fw:
        file_text = fr.read()
        # split on blank line(s) before a JSON object start to support pretty JSONL
        fragments = [f.strip() for f in re.split(r"\n\s*\n(?=\{)", file_text) if f.strip()]
        for frag in fragments:
            try:
                j = json.loads(frag)
            except Exception:
                # skip malformed fragments
                continue
            summary["total"] += 1
            base_text = j.get("cleaned_text") or j.get("raw_output") or ""
            # extract original steps: prefer already-structured `steps` field if present
            if isinstance(j.get('steps'), list) and j.get('steps'):
                orig_steps = j.get('steps')
            else:
                if _extract_steps_from_text:
                    orig_steps = _extract_steps_from_text(base_text)
                else:
                    orig_steps = _extract_steps_fallback(base_text)

            # validate original
            validator = StepQualityValidator()
            qv_orig = validator.evaluate(orig_steps, j.get("instruction", ""), j.get("category", ""))
            alg_orig = validator.validate_algorithm(j.get("instruction", ""), orig_steps)
            hsv_orig = validate_steps_hsv_a(j.get("instruction", ""), orig_steps)

            # rewrite via Flan-T5
            try:
                rewritten_text = rewrite_steps(base_text, model_name=model_name)
            except TypeError:
                # fallback simple rewriter signature: rewrite_steps(text, steps=None)
                rewritten_text = rewrite_steps(base_text, steps=orig_steps)
            if _extract_steps_from_text:
                rewritten_steps = _extract_steps_from_text(rewritten_text)
            else:
                rewritten_steps = _extract_steps_fallback(rewritten_text)

            qv_rew = validator.evaluate(rewritten_steps, j.get("instruction", ""), j.get("category", ""))
            alg_rew = validator.validate_algorithm(j.get("instruction", ""), rewritten_steps)
            hsv_rew = validate_steps_hsv_a(j.get("instruction", ""), rewritten_steps)

            # choose better by algorithmic confidence first, then quality_score
            choose_rewritten = False
            if alg_rew.get("confidence", 0.0) > alg_orig.get("confidence", 0.0):
                choose_rewritten = True
            elif alg_rew.get("confidence", 0.0) == alg_orig.get("confidence", 0.0):
                if qv_rew.get("quality_score", 0.0) > qv_orig.get("quality_score", 0.0):
                    choose_rewritten = True

            out_entry = {
                "instruction": j.get("instruction"),
                "category": j.get("category"),
                "original_steps": orig_steps,
                "original_validation": {"quality": qv_orig, "algorithmic": alg_orig, "hsv": hsv_orig},
                "rewritten_text": rewritten_text,
                "rewritten_steps": rewritten_steps,
                "rewritten_validation": {"quality": qv_rew, "algorithmic": alg_rew, "hsv": hsv_rew},
                "chosen": "rewritten" if choose_rewritten else "original",
                "timestamp": time.time(),
            }
            if choose_rewritten:
                summary["rewrites_better"] += 1
            fw.write(json.dumps(out_entry, ensure_ascii=False) + "\n")
    return summary


if __name__ == "__main__":
    s = process_entries()
    print(f"Processed {s['total']} entries, rewrites better: {s['rewrites_better']}")
