"""Attempt deeper salvage for entries marked `error_in_raw_output`.

Heuristics applied:
- Extract JSON substrings and collect `response` fields.
- Extract any quoted text after 'message' or 'detail' keys.
- Strip common CLI wrapper patterns like "[Ollama run failed: ...]" and keep inner content if present.
- If salvage yields readable text, extract steps via `_extract_steps_from_text` and update main JSONL entry.

Produces:
- `llm_n/salvaged_entries_pretty.jsonl` with successful salvages.
- Updates `llm_n/generated_ollama_pretty.jsonl` replacing entries (matched by instruction+timestamp) when salvaged.
"""
from pathlib import Path
import json
import re
from datetime import datetime

from .ollama_adapter import _extract_steps_from_text

ROOT = Path(__file__).resolve().parent
ERR = ROOT / 'errored_entries_pretty.jsonl'
MAIN = ROOT / 'generated_ollama_pretty.jsonl'
SALV = ROOT / 'salvaged_entries_pretty.jsonl'


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


def extract_responses_from_mixed(raw: str):
    if not raw:
        return ''

    parts = []

    # 1) Find any JSON objects and extract 'response' fields
    for m in re.finditer(r"(\{.*?\})", raw, re.S | re.M):
        chunk = m.group(1)
        try:
            o = json.loads(chunk)
            if isinstance(o, dict):
                if 'response' in o and o.get('response'):
                    parts.append(o.get('response'))
        except Exception:
            # ignore parse errors
            pass

    # 2) Find all occurrences of '"response":"..."' in the whole raw text
    for m in re.finditer(r'"response"\s*:\s*"(.*?)"', raw):
        try:
            txt = m.group(1).encode('utf-8').decode('unicode_escape')
            parts.append(txt)
        except Exception:
            parts.append(m.group(1))

    # 3) Messages or details
    m2 = re.search(r'(?:message|detail|error)"?\s*[:=]\s*"([^"]{5,})"', raw, re.I)
    if m2:
        parts.append(m2.group(1))

    # 4) Strip CLI wrapper patterns like [Ollama run failed: ...]
    m3 = re.search(r'\[Ollama.*?:\s*(.*)\]$', raw)
    if m3:
        inner = m3.group(1)
        # remove trailing 'returned non-zero...' messages
        inner = re.sub(r"returned non-zero exit status.*$", '', inner)
        parts.append(inner.strip())

    # 5) If still empty, try to capture any long plain text sequences
    if not parts:
        longtxt = re.findall(r'([A-Z][^\n]{50,})', raw)
        for t in longtxt:
            parts.append(t.strip())

    if not parts:
        return ''

    joined = ''.join(parts)
    # Normalize whitespace
    joined = joined.replace('\\n', '\n')
    joined = re.sub(r'\s+', ' ', joined)
    return joined.strip()


def main():
    errored = read_pretty_jsonl(ERR)
    if not errored:
        print('No errored entries found in', ERR)
        return

    main_objs = read_pretty_jsonl(MAIN)
    salvaged = []
    updated = 0

    for e in errored:
        raw = e.get('raw_output') or ''
        instr = e.get('instruction')
        ts = e.get('timestamp')
        print('Attempting salvage for:', instr)
        cleaned = extract_responses_from_mixed(raw)
        if not cleaned or len(cleaned) < 20:
            e['salvage_attempted'] = True
            e['salvage_note'] = 'No readable content extracted'
            continue

        steps = _extract_steps_from_text(cleaned)
        if not steps:
            e['salvage_attempted'] = True
            e['salvage_note'] = 'Extraction produced no steps'
            e['cleaned_text'] = cleaned
            continue

        # Update matching entry in main_objs by instruction + timestamp (best-effort)
        matched = False
        for m in main_objs:
            if m.get('instruction') == instr and (not ts or m.get('timestamp') == ts):
                m['cleaned_text'] = cleaned
                m['steps'] = steps
                m['total_steps'] = len(steps)
                m['status'] = 'salvaged'
                m['salvaged_at'] = datetime.utcnow().isoformat()
                matched = True
                updated += 1
                salvaged.append(m)
                break

        if not matched:
            # Append new salvaged record
            rec = {
                'instruction': instr,
                'category': e.get('category'),
                'steps': steps,
                'total_steps': len(steps),
                'status': 'salvaged',
                'raw_output': raw,
                'cleaned_text': cleaned,
                'timestamp': datetime.utcnow().isoformat(),
                'salvaged_at': datetime.utcnow().isoformat()
            }
            main_objs.append(rec)
            salvaged.append(rec)
            updated += 1

    # Write salvaged entries file
    if salvaged:
        with SALV.open('w', encoding='utf-8') as f:
            for s in salvaged:
                f.write(json.dumps(s, indent=4, ensure_ascii=False))
                f.write('\n\n')

    # Overwrite main JSONL
    if main_objs:
        with MAIN.open('w', encoding='utf-8') as f:
            for o in main_objs:
                f.write(json.dumps(o, indent=4, ensure_ascii=False))
                f.write('\n\n')

    print(f'Salvaged {updated} entries; wrote {len(salvaged)} salvaged records to {SALV}')


if __name__ == '__main__':
    main()
