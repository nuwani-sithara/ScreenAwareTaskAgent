import json

data = [json.loads(l) for l in open('automation_dataset.jsonl')]
print(f'Total examples: {len(data)}')

# Check first example
print(f'\n1st example:')
print(f"Instruction: {data[0]['instruction']}")
print(f"Output: {data[0]['output']}")

# Check login example
login_examples = [d for d in data if 'login' in d['instruction'].lower()]
print(f'\n{len(login_examples)} login examples')
if login_examples:
    print(f"Login example 1: {login_examples[0]['output'][:150]}")

# Check file-related
file_examples = [d for d in data if 'file' in d['instruction'].lower()]
print(f'\n{len(file_examples)} file-related instructions')
for i, ex in enumerate(file_examples[:3]):
    print(f"\n{i+1}. {ex['instruction']}")
    print(f"   Output: {ex['output'][:100]}...")
