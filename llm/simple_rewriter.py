from typing import List, Optional
from llm.step_validators import normalize_verb


def _clean_action(action: str) -> str:
    a = action.strip()
    # remove leading "Step N:" or similar
    import re
    a = re.sub(r"^Step\s*\d+\s*[:\-]\s*", "", a, flags=re.I)
    # ensure starts with verb; if not, try to move first noun into an imperative
    words = a.split()
    if not words:
        return a
    first = words[0].lower()
    # only prepend a generic verb when the first token is a determiner or stopword
    stopwords = set(('the', 'a', 'an', 'to', 'for', 'on', 'in', 'of', 'by'))
    verb_like = set(('open','click','select','enter','press','choose','focus','run','start','stop','save','load','install','create','generate','move','type','verify','wait','check','merge','plan','implement','execute','press'))
    if first in stopwords:
        a = 'Open ' + a
    elif first not in verb_like:
        # If first token looks capitalized but likely a verb (e.g., 'Merge'), assume it's fine.
        # Otherwise leave as-is rather than forcing 'Open'.
        pass
    # strip trailing periods
    a = a.rstrip('. ')
    return a


def rewrite_steps(text: str, steps: Optional[List[dict]] = None) -> str:
    """Rule-based rewrite: produce concise numbered, imperative steps as text.

    If `steps` (structured) is provided, prefer it; otherwise attempt to split `text` by lines.
    """
    out_lines = []
    if steps and isinstance(steps, list) and len(steps) > 0:
        for idx, s in enumerate(steps, start=1):
            action = s.get('action') if isinstance(s, dict) else str(s)
            a = _clean_action(action)
            out_lines.append(f"{idx}. {a}")
        return "\n".join(out_lines)

    # fallback: split text into lines and attempt to clean
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        # fallback to entire text as single step
        return "1. " + _clean_action(text)
    for idx, l in enumerate(lines, start=1):
        out_lines.append(f"{idx}. {_clean_action(l)}")
    return "\n".join(out_lines)


if __name__ == "__main__":
    sample = "Step 1: Focus on the app.\nStep 2: Click the add button."
    print(rewrite_steps(sample, steps=None))
