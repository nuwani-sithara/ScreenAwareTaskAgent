"""Validate generated outputs in `llm_n/generated_ollama_pretty.jsonl`.

Produces `llm_n/validation_results_pretty.jsonl` and prints a concise summary.

Checks performed (lightweight):
- JSON parsed
- `steps` exists and non-empty
- `raw_output` doesn't contain obvious error tokens (failed/error/traceback)
- all steps have non-empty `action`
- step numbers are sequential starting at 1
"""
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'generated_ollama_pretty.jsonl'
OUTPUT = ROOT / 'validation_results_pretty.jsonl'


def read_pretty_jsonl(p: Path):
    if not p.exists():
        return []
    text = p.read_text(encoding='utf-8')
    # Split on blank lines between pretty JSON blocks
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    objs = []
    for b in blocks:
        try:
            objs.append(json.loads(b))
        except Exception:
            # skip invalid blocks
            continue
    return objs


def validate_entry(entry: dict):
    problems = []
    raw = (entry.get('raw_output') or '')
    steps = entry.get('steps') or []

    # Basic checks
    if not steps:
        problems.append('no_steps')

    lowered = raw.lower()
    if any(tok in lowered for tok in ('failed', 'error', 'traceback')):
        problems.append('error_in_raw_output')

    # step content
    for s in steps:
        act = (s.get('action') or '')
        if not act.strip() or len(act.strip()) < 3:
            problems.append('short_or_empty_action')
            break

    # step numbering
    try:
        nums = [int(s.get('step', i+1)) for i, s in enumerate(steps)]
        if nums and nums != list(range(1, len(nums)+1)):
            problems.append('nonsequential_steps')
    except Exception:
        problems.append('step_number_parse_error')

    status = 'PASS' if not problems else 'FAIL'
    return {'instruction': entry.get('instruction'), 'status': status, 'problems': problems, 'timestamp': datetime.utcnow().isoformat(), 'total_steps': len(steps)}


def main():
    objs = read_pretty_jsonl(INPUT)
    results = []
    for o in objs:
        res = validate_entry(o)
        results.append(res)

    # Write pretty JSONL output
    with OUTPUT.open('a', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, indent=4, ensure_ascii=False))
            f.write('\n\n')

    # Print concise summary
    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = total - passed
    print('Validation summary')
    print('==================')
    print(f'Total entries checked: {total}')
    print(f'Passed: {passed}  Failed: {failed}')
    if failed:
        print('\nFailures (first 10):')
        for r in results[:10]:
            if r['status'] == 'FAIL':
                print(f"- {r['instruction']}: {r['problems']}")


if __name__ == '__main__':
    main()
