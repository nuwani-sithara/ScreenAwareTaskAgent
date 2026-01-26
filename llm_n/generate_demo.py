"""Demo runner that uses `OllamaClient` to generate outputs and save them as pretty JSONL.

Usage:
    python generate_demo.py --model mistral --prompt "Play 2048 game: restart game"

This will print output and append a pretty JSON block to `llm_n/generated_ollama_pretty.jsonl`.
"""
import argparse
import json
import os
from datetime import datetime

from llm_n.ollama_client import OllamaClient


def save_pretty(result: dict, path: str):
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(result, ensure_ascii=False, indent=4))
        fh.write('\n\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='mistral', help='Ollama model name (mistral / llama...)')
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--out', default='generated_ollama_pretty.jsonl')
    args = parser.parse_args()

    client = OllamaClient()
    print(f"Using model: {args.model}")
    text = client.generate(args.prompt, model=args.model)

    result = {
        'instruction': args.prompt,
        'model': args.model,
        'output': text,
        'timestamp': datetime.utcnow().isoformat()
    }

    # Save to package-relative file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(current_dir, args.out)
    save_pretty(result, out_path)

    print('--- Generated ---')
    print(text)
    print(f'Saved pretty result to: {out_path}')


if __name__ == '__main__':
    main()
