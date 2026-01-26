"""
Verify your training dataset is correctly formatted
This script checks your llm_dataset.jsonl file
"""
import json
import os

def verify_dataset():
    print("🔍 DATASET VERIFICATION TOOL")
    print("="*60)
    
    dataset_file = "llm_dataset.jsonl"
    
    if not os.path.exists(dataset_file):
        print(f"❌ Error: {dataset_file} not found!")
        return
    
    print(f"✅ Found: {dataset_file}\n")
    
    # Read and validate
    valid_count = 0
    invalid_count = 0
    errors = []
    
    with open(dataset_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                data = json.loads(line)
                
                # Check required fields
                if 'instruction' not in data:
                    errors.append(f"Line {line_num}: Missing 'instruction' field")
                    invalid_count += 1
                    continue
                    
                if 'output' not in data:
                    errors.append(f"Line {line_num}: Missing 'output' field")
                    invalid_count += 1
                    continue
                
                # Check if fields are non-empty
                if not data['instruction'].strip():
                    errors.append(f"Line {line_num}: Empty instruction")
                    invalid_count += 1
                    continue
                    
                if not data['output'].strip():
                    errors.append(f"Line {line_num}: Empty output")
                    invalid_count += 1
                    continue
                
                valid_count += 1
                
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")
                invalid_count += 1
    
    # Results
    print(f"📊 VALIDATION RESULTS:")
    print(f"   Total lines: {valid_count + invalid_count}")
    print(f"   ✅ Valid entries: {valid_count}")
    print(f"   ❌ Invalid entries: {invalid_count}")
    
    if errors:
        print(f"\n⚠️  ERRORS FOUND:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"   - {error}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
    else:
        print(f"\n✅ ALL ENTRIES ARE VALID!")
    
    # Show sample entries
    print(f"\n📝 SAMPLE ENTRIES (first 3):")
    with open(dataset_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if i > 3:
                break
            data = json.loads(line)
            print(f"\n   Entry {i}:")
            print(f"   Instruction: {data.get('instruction', 'N/A')[:60]}...")
            print(f"   Output: {data.get('output', 'N/A')[:60]}...")
    
    print(f"\n{'='*60}")
    
    if invalid_count == 0:
        print("✅ Your dataset is correctly formatted for training!")
        print("✅ Ready to use for fine-tuning LLM models")
    else:
        print("⚠️  Please fix the errors before training")
        print("💡 Each line must be valid JSON with 'instruction' and 'output' fields")

if __name__ == "__main__":
    verify_dataset()
