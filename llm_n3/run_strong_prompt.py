"""Run a stronger, imperative prompt against Ollama and output cleaned numbered UI steps.

Usage: python -m llm_n.run_strong_prompt
"""
import json
import re
from pathlib import Path

from .ollama_client import OllamaClient
from .ollama_adapter import _extract_steps_from_text

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'strong_prompt_output.json'


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
            m = re.search(r"(\{.*\})", line)
            if m:
                try:
                    obj = json.loads(m.group(1))
                    if isinstance(obj, dict) and 'response' in obj:
                        parts.append(obj.get('response') or '')
                        continue
                except Exception:
                    pass
        m2 = re.findall(r'"response"\s*:\s*"(.*?)"', line)
        if m2:
            for m3 in m2:
                try:
                    parts.append(json.loads(f'"{m3}"'))
                except Exception:
                    parts.append(m3)
            continue
        parts.append(line)

    joined = ''.join(parts)
    joined = joined.replace('\\n', '\n')
    joined = re.sub(r'\s+', ' ', joined)
    return joined.strip()


def enforce_format(steps):
    # Ensure strong action verb start and sentence capitalization
    verbs = ('Open','Click','Enter','Select','Navigate','Verify','Tap','Press','Choose')
    out = []
    for s in steps:
        action = s.get('action','').strip()
        if not action:
            continue
        # Capitalize first letter
        action = action[0].upper() + action[1:]
        # If first word not a strong verb, leave as-is (do not invent actions)
        first = action.split()[0].rstrip(':,').capitalize()
        if first not in verbs:
            # try to detect imperative verb and capitalize
            words = action.split()
            if words:
                words[0] = words[0].capitalize()
                action = ' '.join(words)
        out.append(action)
    # Reindex steps
    return [{ 'step': i+1, 'action': a, 'description': f"Step {i+1}: {a}" } for i,a in enumerate(out)]


def main():
    user_instruction = 'can you add like this prompt'

    prompt = (
        "You are a human-like UI test automation agent.\n"
        "Your task is to convert a user's instruction into clear, executable UI test steps.\n"
        "Rules:\n"
        "- Generate only UI interaction steps.\n"
        "- Each step must start with a strong action verb (Open, Click, Enter, Select, Navigate, Verify).\n"
        "- Steps must be sequential and logical.\n"
        "- Do NOT include planning, coding, or implementation steps.\n"
        "- Do NOT explain — only output the steps.\n\n"
        "Format:\n"
        "Steps:\n"
        "1. <Step one>\n"
        "2. <Step two>\n"
        "...\n\n"
        "Instruction: " + user_instruction + "\n\n"
        "Additional constraints: Provide exactly 3 steps. Use full sentences. Start each step with a single imperative verb. Do not include any additional text."
    )

    client = OllamaClient()
    raw = client.generate(prompt, model='mistral')
    cleaned = clean_stream_text(raw)
    steps = _extract_steps_from_text(cleaned)
    steps = enforce_format(steps[:3])

    output = {
        'instruction': user_instruction,
        'raw_output': raw,
        'cleaned_text': cleaned,
        'steps': steps,
        'total_steps': len(steps)
    }

    OUT.write_text(json.dumps(output, indent=4, ensure_ascii=False), encoding='utf-8')

    # Print in required simple format
    print('Steps:')
    for s in steps:
        print(f"{s['step']}. {s['action']}")


if __name__ == '__main__':
    main()
