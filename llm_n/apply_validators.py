"""Apply richer validators from `llm` to normalized generations and update JSONL.

Usage: python -m llm_n.apply_validators
"""
from pathlib import Path
import json
import re
from datetime import datetime

from llm.step_validators import StepQualityValidator, validate_steps_hsv_a
from .ollama_adapter import _extract_steps_from_text

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'generated_ollama_pretty.jsonl'
OUT = ROOT / 'validation_results_pretty.jsonl'


def read_pretty_jsonl(p: Path):
    if not p.exists():
        return []
    import re
    text = p.read_text(encoding='utf-8')
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    objs = []
    for b in blocks:
        try:
            objs.append(json.loads(b))
        except Exception:
            continue
    return objs


def write_pretty_jsonl(objs, p: Path):
    with p.open('w', encoding='utf-8') as f:
        for o in objs:
            f.write(json.dumps(o, indent=4, ensure_ascii=False))
            f.write('\n\n')


def looks_like_failure_text(s: str) -> bool:
    if not s:
        return False
    low = s.lower()
    return any(tok in low for tok in ('ollama generate failed', 'ollama run failed', 'winerror', 'returned non-zero', 'failed to'))


def clean_and_extract(entry):
    # Prefer cleaned_text if present
    text = entry.get('cleaned_text') or entry.get('raw_output') or ''
    # If text contains CLI error wrappers but also contains JSON streaming fragments,
    # try to salvage via regex to pull quoted 'response' values.
    if looks_like_failure_text(text):
        # try to salvage any quoted message after 'message' or similar
        m = re.search(r'message"?\s*[:=]\s*"([^"]{20,})"', text)
        if m:
            text = m.group(1)
        else:
            # nothing salvageable
            return []

    # Use adapter extractor
    steps = _extract_steps_from_text(text)
    # Filter out placeholder steps
    filtered = []
    for s in steps:
        action = (s.get('action') or '').strip()
        if not action:
            continue
        if looks_like_failure_text(action):
            continue
        filtered.append(s)

    # Reindex sequentially
    for i, s in enumerate(filtered, 1):
        s['step'] = i

    return filtered


def main():
    objs = read_pretty_jsonl(INPUT)
    if not objs:
        print('No entries found in', INPUT)
        return

    validator = StepQualityValidator()
    results = []
    updated_objs = []

    for entry in objs:
        instr = entry.get('instruction')
        steps = entry.get('steps') or []
        # If steps look like placeholders or are empty, try to extract from cleaned_text
        need_extraction = False
        if not steps:
            need_extraction = True
        else:
            # detect placeholder contents
            if any(looks_like_failure_text(s.get('action','')) for s in steps):
                need_extraction = True

        if need_extraction:
            new_steps = clean_and_extract(entry)
            if new_steps:
                entry['steps'] = new_steps
                entry['total_steps'] = len(new_steps)
            else:
                entry['steps'] = []
                entry['total_steps'] = 0

        # Run richer validators
        quality = validator.evaluate(entry.get('steps', []), instruction=instr, category=entry.get('category'))
        alg = validator.validate_algorithm(instr, entry.get('steps', []), dataset_patterns=None)
        hsv = validate_steps_hsv_a(instr, entry.get('steps', []), dataset_patterns={'avg_steps': max(1, entry.get('total_steps',1))}, similarity_score=None)

        validation_record = {
            'instruction': instr,
            'timestamp': datetime.utcnow().isoformat(),
            'quality': quality,
            'algorithmic': alg,
            'hsv': hsv,
            'steps_count': entry.get('total_steps', 0),
        }

        # Decide status
        passed = alg.get('is_valid') or hsv.get('is_valid') or (quality.get('quality_score',0) > 0.6)
        if passed:
            entry['status'] = 'validated'
        else:
            # keep earlier error flag if present
            if entry.get('status') == 'error_in_raw_output':
                entry['status'] = 'error_in_raw_output'
            else:
                entry['status'] = 'needs_review'

        entry['validation'] = validation_record
        results.append(validation_record)
        updated_objs.append(entry)

    # Overwrite main JSONL with updated entries (cleaned steps and statuses)
    write_pretty_jsonl(updated_objs, INPUT)
    # Write validation results
    write_pretty_jsonl(results, OUT)

    # Summary
    passed = sum(1 for r in results if r['algorithmic'].get('is_valid') or r['hsv'].get('is_valid') or r['quality'].get('quality_score',0) > 0.6)
    total = len(results)
    print(f'Applied validators to {total} entries — passed: {passed}, failed: {total-passed}. Results in {OUT}')


if __name__ == '__main__':
    main()
