import csv
import json
from pathlib import Path

def write_report(input_path='llm_n/hybrid_results_pretty.jsonl', out_csv='llm_n/hybrid_report.csv'):
    p = Path(input_path)
    rows = []
    if not p.exists():
        print(input_path, 'not found')
        return
    with p.open('r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            j = json.loads(line)
            rows.append({
                'instruction': j.get('instruction'),
                'chosen': j.get('chosen'),
                'orig_alg_conf': j.get('original_validation', {}).get('algorithmic', {}).get('confidence'),
                'rew_alg_conf': j.get('rewritten_validation', {}).get('algorithmic', {}).get('confidence'),
                'orig_quality': j.get('original_validation', {}).get('quality', {}).get('quality_score'),
                'rew_quality': j.get('rewritten_validation', {}).get('quality', {}).get('quality_score'),
            })

    with open(out_csv, 'w', newline='', encoding='utf-8') as csvf:
        writer = csv.DictWriter(csvf, fieldnames=['instruction','chosen','orig_alg_conf','rew_alg_conf','orig_quality','rew_quality'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print('Wrote', out_csv)

if __name__ == '__main__':
    write_report()
