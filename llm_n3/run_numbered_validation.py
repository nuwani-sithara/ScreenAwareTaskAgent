"""Generate numbered steps with Ollama, clean streaming fragments, extract steps, and validate.

Saves output to `llm_n/numbered_validation_output.json`.
"""
import json
from pathlib import Path
from datetime import datetime
import re

from .ollama_client import OllamaClient
from .ollama_adapter import _extract_steps_from_text
from llm.step_validators import StepQualityValidator, validate_steps_hsv_a

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'numbered_validation_output.json'


def clean_stream_text(raw: str) -> str:
    parts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and 'response' in obj:
                parts.append(obj.get('response') or '')
                continue
        except Exception:
            # try to extract JSON substring
            m = re.search(r"(\{.*\})", line)
            if m:
                try:
                    obj = json.loads(m.group(1))
                    if isinstance(obj, dict) and 'response' in obj:
                        parts.append(obj.get('response') or '')
                        continue
                except Exception:
                    pass
        # fallback: attempt to extract "response":"..."
        m2 = re.findall(r'"response"\s*:\s*"(.*?)"', line)
        if m2:
            for m3 in m2:
                try:
                    parts.append(json.loads(f'"{m3}"'))
                except Exception:
                    parts.append(m3)
            continue
        # plain text
        parts.append(line)

    joined = ''.join(parts)
    joined = joined.replace('\\n', '\n')
    joined = re.sub(r'\s+', ' ', joined)
    return joined.strip()


def main():
    prompt = (
        "Provide 5 numbered steps to add a product to the cart. "
        "Use full sentences, start each step with an imperative verb (e.g., 'Click', 'Open'), "
        "and format them as: 1. Step sentence\n2. Step sentence\n..."
    )

    client = OllamaClient()
    raw = client.generate(prompt, model='mistral')
    cleaned = clean_stream_text(raw)

    steps = _extract_steps_from_text(cleaned)

    v = StepQualityValidator()
    quality = v.evaluate(steps, instruction=prompt)
    alg = v.validate_algorithm(prompt, steps)
    hsv = validate_steps_hsv_a(prompt, steps, dataset_patterns={'avg_steps': max(1, len(steps))})

    out = {
        'prompt': prompt,
        'raw_output': raw,
        'cleaned_text': cleaned,
        'steps': steps,
        'total_steps': len(steps),
        'validation': {
            'quality': quality,
            'algorithmic': alg,
            'hsv': hsv,
            'timestamp': datetime.utcnow().isoformat()
        }
    }

    OUT.write_text(json.dumps(out, indent=4, ensure_ascii=False), encoding='utf-8')
    print('Generated', len(steps), 'steps — quality:', quality.get('quality_score'), 'alg_conf:', alg.get('confidence'), 'hsv_conf:', hsv.get('confidence'))
    print('Saved to', OUT)


if __name__ == '__main__':
    main()
