"""Generate and validate a single instruction using Ollama integration.

Writes result to `llm_n/single_validation_output.json` and prints concise summary.
"""
import json
from pathlib import Path

from llm.step_validators import StepQualityValidator, validate_steps_hsv_a
from .ollama_adapter import generate_and_format

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'single_validation_output.json'


def main():
    instr = 'add product to the cart'
    print('Generating for instruction:', instr)
    try:
        res = generate_and_format(instr, model='mistral')
    except Exception as e:
        print('Generation failed:', e)
        return

    steps = res.get('steps', [])

    v = StepQualityValidator()
    quality = v.evaluate(steps, instruction=res.get('instruction'))
    alg = v.validate_algorithm(res.get('instruction'), steps)
    hsv = validate_steps_hsv_a(res.get('instruction'), steps, dataset_patterns={'avg_steps': max(1, len(steps))})

    out = {
        'instruction': instr,
        'generated': res,
        'quality': quality,
        'algorithmic': alg,
        'hsv': hsv,
    }

    OUT.write_text(json.dumps(out, indent=4, ensure_ascii=False), encoding='utf-8')

    print('\nValidation summary:')
    print(' - steps_count:', len(steps))
    print(' - quality_score:', quality.get('quality_score'))
    print(' - algorithmic.confidence:', alg.get('confidence'), 'is_valid=', alg.get('is_valid'))
    print(' - hsv.confidence:', hsv.get('confidence'), 'is_valid=', hsv.get('is_valid'))
    decision = 'ACCEPT' if alg.get('is_valid') or hsv.get('is_valid') or quality.get('quality_score',0) > 0.6 else 'REVIEW'
    print(' - decision:', decision)
    print('\nSaved full output to', OUT)


if __name__ == '__main__':
    main()
