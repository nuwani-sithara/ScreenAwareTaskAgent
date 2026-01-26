"""Normalize streaming `raw_output` fields in `generated_ollama_pretty.jsonl`.

This script:
- Reads pretty JSONL entries from `generated_ollama_pretty.jsonl`.
- For entries whose `raw_output` contains Ollama streaming JSON-lines, it
  parses the lines, concatenates the `response` fragments, cleans whitespace,
  extracts structured `steps` via the existing adapter, and replaces the
  `steps` / `total_steps` / `status` fields with cleaned values.
- Writes the updated entries back to the same file (overwrites).

Run: python -m llm_n.normalize_streams
"""
from pathlib import Path
import json
import re
from datetime import datetime

from .ollama_adapter import _extract_steps_from_text


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'generated_ollama_pretty.jsonl'


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


def extract_responses_from_raw(raw: str):
    if not raw:
        return '', False
    low = raw.lower()
    # Quick-detect common CLI / subprocess error messages that should be treated as errors
    if 'ollama generate failed' in low or 'returned non-zero exit status' in low or 'winerror' in low:
        return raw, True
    parts = []
    saw_error = False
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = None
        # Try full-line JSON
        try:
            parsed = json.loads(line)
        except Exception:
            # Try to extract a JSON substring
            m = re.search(r"(\{.*\})", line)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                except Exception:
                    parsed = None

        if isinstance(parsed, dict):
            # If the stream reported an error, mark and continue
            if parsed.get('error') or parsed.get('status') == 'error' or parsed.get('code') == 'error':
                saw_error = True
                continue
            # Common Ollama streaming envelope uses 'response'
            if 'response' in parsed:
                parts.append(parsed.get('response') or '')
                continue
            # Otherwise try to find plausible string values
            for v in parsed.values():
                if isinstance(v, str) and v.strip():
                    parts.append(v)
                    break
            continue

        # Not JSON: strip common SSE prefixes like 'data:' or 'event:'
        if line.startswith('data:'):
            line = line.split(':', 1)[1].strip()
        elif line.startswith('event:'):
            line = line.split(':', 1)[1].strip()

        # If the line contains a response key with quotes, try regex
        m2 = re.search(r'"response"\s*:\s*"(.*?)"', line)
        if m2:
            resp = m2.group(1).encode('utf-8').decode('unicode_escape')
            parts.append(resp)
            continue

        # Otherwise include the cleaned line
        parts.append(line)

    if saw_error and not parts:
        # return error indicator when parsing produced only errors
        return raw, True

    if not parts:
        return raw, False

    # Join fragments preserving deliberate leading spaces in fragments
    joined = ''.join(parts)
    # Normalize escaped newlines and repeated whitespace
    joined = joined.replace('\\n', '\n')
    # Collapse sequences of whitespace but preserve newline markers
    joined = re.sub(r'[ \t\f\v]+', ' ', joined)
    joined = re.sub(r'\n\s+', '\n', joined)
    return joined.strip(), False


def main():
    objs = read_pretty_jsonl(INPUT)
    updated = []
    for entry in objs:
        raw = entry.get('raw_output') or ''
        cleaned, error_flag = extract_responses_from_raw(raw)
        if error_flag:
            entry['cleaned_text'] = cleaned
            entry['steps'] = []
            entry['total_steps'] = 0
            entry['status'] = 'error_in_raw_output'
            entry['normalized_at'] = datetime.utcnow().isoformat()
            updated.append(entry)
            continue

        # If cleaned is meaningfully different, extract steps
        steps = _extract_steps_from_text(cleaned)
        entry['cleaned_text'] = cleaned
        entry['steps'] = steps
        entry['total_steps'] = len(steps)
        entry['status'] = 'ready_for_execution' if len(steps) > 0 else 'needs_review'
        entry['normalized_at'] = datetime.utcnow().isoformat()
        updated.append(entry)

    # Overwrite file with updated pretty JSON blocks
    with INPUT.open('w', encoding='utf-8') as f:
        for e in updated:
            f.write(json.dumps(e, indent=4, ensure_ascii=False))
            f.write('\n\n')

    # Write errored / review-needed entries to a separate file for manual inspection
    ERR = ROOT / 'errored_entries_pretty.jsonl'
    errored = [e for e in updated if e.get('status') in ('error_in_raw_output', 'needs_review')]
    if errored:
        with ERR.open('w', encoding='utf-8') as ef:
            for e in errored:
                # include a short excerpt for reviewer convenience
                ex = (e.get('raw_output') or '')[:400]
                e['error_excerpt'] = ex
                ef.write(json.dumps(e, indent=4, ensure_ascii=False))
                ef.write('\n\n')

    print(f'Normalized {len(updated)} entries and updated {INPUT}')
    if errored:
        print(f'Wrote {len(errored)} errored entries to {ERR}')


if __name__ == '__main__':
    main()
