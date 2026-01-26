"""Retry generation for entries saved in `errored_entries_pretty.jsonl`.

This script reads the errored entries file, re-runs generation for each
instruction using the current Ollama client via `ollama_adapter.generate_and_format`,
and appends the new result to `generated_ollama_pretty.jsonl` for normalization.

Run: python -m llm_n.retry_errored
"""
from pathlib import Path
import json
from datetime import datetime

from .ollama_adapter import generate_and_format

ROOT = Path(__file__).resolve().parent
ERR = ROOT / 'errored_entries_pretty.jsonl'
OUT = ROOT / 'generated_ollama_pretty.jsonl'


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


def append_pretty(obj, p: Path):
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, indent=4, ensure_ascii=False))
        f.write('\n\n')


def main():
    errored = read_pretty_jsonl(ERR)
    if not errored:
        print('No errored entries to retry.')
        return

    retried = 0
    for e in errored:
        instr = e.get('instruction')
        if not instr:
            continue
        print(f'Retrying: {instr!r}')
        try:
            res = generate_and_format(instr, model=e.get('model', 'mistral'))
            # add retry metadata
            res['retried_from'] = instr
            res['retried_at'] = datetime.utcnow().isoformat()
            append_pretty(res, OUT)
            retried += 1
        except Exception as ex:
            print('Retry failed for:', instr, ex)

    print(f'Retried {retried} entries and appended to {OUT}')


if __name__ == '__main__':
    main()
