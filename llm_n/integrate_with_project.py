"""Integrate Ollama adapter outputs into the project's pretty JSON log.

Usage:
    python -m llm_n.integrate_with_project --prompt "Play 2048 game: restart game"

This script lives in `llm_n/` and will write to `../llm/generated_steps_pretty.jsonl` by default.
"""
import argparse
import json
import os
from datetime import datetime

from .ollama_adapter import generate_and_format


def save_to_project(result: dict, out_path: str):
    # Ensure directory exists
    dirp = os.path.dirname(out_path)
    if dirp and not os.path.exists(dirp):
        try:
            os.makedirs(dirp, exist_ok=True)
        except Exception:
            pass

    # Append pretty JSON block
    with open(out_path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(result, ensure_ascii=False, indent=4))
        fh.write('\n\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='mistral')
    parser.add_argument('--prompt', required=True)
    # Default output placed inside the `llm_n` package for local testing
    parser.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_ollama_pretty.jsonl'))
    args = parser.parse_args()

    res = generate_and_format(args.prompt, model=args.model)
    # Add a timestamp override to ensure ISO format
    res['timestamp'] = datetime.utcnow().isoformat()

    save_to_project(res, args.out)
    print(f"Saved formatted result to: {os.path.abspath(args.out)}")


if __name__ == '__main__':
    main()
