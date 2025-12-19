# Step Validation System

## Quick Start

The validation system automatically validates steps generated for user instructions against your JSONL dataset files.

### Interactive Validation
```bash
python demo.py
```
When you enter an instruction, you'll get:
- Generated steps
- Validation results with confidence score
- Matched instruction from dataset
- Warnings/issues if any

### Batch Validation
```bash
python demo.py --test
```
Runs predefined test cases and generates a summary report showing:
- Per-instruction validation results
- Overall success rate
- Detailed breakdown

### Single Instruction Validation
```bash
python validate_steps.py --single "Create a JS app to add 2 numbers"
```
Generates detailed validation report for one instruction.

### Batch Custom Validation
```bash
python validate_steps.py --batch "Instruction 1" "Instruction 2"
```

## What Gets Validated

### 1. **Format Validation**
✓ All required fields present (`step`, `action`, `description`)  
✓ Step numbers are sequential  
✓ Each action is non-empty and >5 characters  
✓ Proper JSON structure  

### 2. **Dataset Matching**
✓ Finds most similar instruction in your JSONL files  
✓ Compares against `llm_dataset.jsonl` (79 examples)  
✓ Compares against `rag_2048.jsonl` (47 examples)  

### 3. **Similarity Scoring**
✓ Measures text similarity (0-100%)  
✓ Checks step count matching  
✓ Compares action descriptions  

### 4. **Confidence Scoring**
✓ 95%+: Excellent match with dataset → Execute immediately  
✓ 70-94%: Good match → Safe to use  
✓ 50-69%: Valid but different → Review first  
✓ <50%: Poor match → Consider regenerating  

### 5. **Category-Specific Validation**
- **Game 2048**: Checks for game-specific keywords (focus, window, game)
- **Software Dev**: Checks for development keywords (create, button, input, output)

## Validation Output

### Example Output
```
✅ VALIDATION RESULTS:
   Status: ✓ VALID
   Confidence: 95.0%
   Similarity: 100.0%
   Matched: 'Create a JS app to add 2 numbers'
```

### Validation Result JSON
```json
{
  "validation": {
    "is_valid": true,
    "confidence": 0.95,
    "similarity": 1.0,
    "matched_instruction": "Create a JS app to add 2 numbers",
    "format_valid": true,
    "issues": [],
    "warnings": []
  }
}
```

## Understanding Results

### ✓ VALID Status
- All format checks pass
- Confidence ≥ 50%
- No critical issues
- Ready for execution

### ✗ INVALID Status
- Format validation failed
- Critical issues found
- Confidence < 50%
- Needs regeneration/review

### Confidence Interpretation
- **95%**: Perfect or near-perfect match with dataset
- **70%**: Good match, dataset similar example found
- **50%**: Valid but differs from dataset examples
- **30%**: Poor match, consider regeneration

## Datasets

### llm_dataset.jsonl (79 examples)
- General software development
- Arithmetic operations: add, subtract, multiply, divide
- JavaScript and Python examples
- Format: HTML forms, input fields, buttons

### rag_2048.jsonl (47 examples)
- 2048 game automation
- Game operations: start, restart, swipes
- Movement directions: left, right, up, down

## Advanced Usage

### Generate Detailed Report
```python
from demo import generate_validation_report

report = generate_validation_report("Create a JS app to add 2 numbers")

print(f"Valid: {report['validation_details']['is_valid']}")
print(f"Confidence: {report['validation_details']['confidence']:.1%}")
print(f"Recommendation: {report['recommendation']}")
```

### Batch Testing with Results
```python
from demo import SimpleAssistant

assistant = SimpleAssistant()
instructions = [
    "Create a JS app to add 2 numbers",
    "Play 2048 game: swipe left",
    "Some unrelated instruction"
]

for instr in instructions:
    result = assistant.process_instruction(instr)
    validation = result['validation']
    print(f"{instr}: {validation['confidence']:.1%} confidence")
```

### Access Validator Directly
```python
from demo import StepValidator

validator = StepValidator()

# Validate generated steps
validation_result = validator.validate_steps(
    instruction="Create a JS app to add 2 numbers",
    steps=[
        {"step": 1, "action": "Create input fields", "description": "..."},
        {"step": 2, "action": "Create output field", "description": "..."}
    ],
    category="general_software"
)

print(f"Valid: {validation_result['is_valid']}")
print(f"Confidence: {validation_result['confidence']:.1%}")
print(f"Issues: {validation_result['issues']}")
print(f"Warnings: {validation_result['warnings']}")
```

## Troubleshooting

### Low Confidence Scores
**Problem**: Generated steps have <70% confidence
**Cause**: Steps differ from dataset examples
**Solution**:
1. Check matched instruction - is it similar to your intent?
2. Add more examples to dataset if instruction type is new
3. Review generated steps for obvious errors
4. Ensure instruction is clear and specific

### Format Validation Failures
**Problem**: "Format errors" in validation
**Cause**: Steps missing required fields or invalid structure
**Solution**:
1. Verify each step has: `step`, `action`, `description`
2. Check step numbers are 1, 2, 3... (sequential)
3. Ensure each action is >5 characters
4. No empty actions

### No Dataset Match Found
**Problem**: "No similar instruction found in dataset"
**Cause**: 
- Instruction is very different from existing examples
- Datasets are too small for this instruction type
**Solution**:
1. Expand dataset with more examples
2. Use fallback generic steps
3. Review dataset coverage for your use case

## Performance Notes

- **Initialization**: ~5-10 seconds (loads datasets + model)
- **Per-instruction**: ~2-5 seconds (model inference + validation)
- **Memory**: ~2-3 GB (fine-tuned model)
- **Validation overhead**: <100ms per instruction

## File Structure

```
llm/
├── demo.py                      # Main demo with validation
├── validate_steps.py            # Standalone validation script
├── llm_dataset.jsonl           # General software examples (79)
├── rag_2048.jsonl              # 2048 game examples (47)
├── VALIDATION_GUIDE.md         # Detailed guide
├── VALIDATION_README.md        # This file
└── fine_tuned_js_model/
    └── checkpoint-3/           # Fine-tuned model weights
```

## Integration Example

```python
# In your backend/main.py
from llm.demo import SimpleAssistant

# Initialize once
assistant = SimpleAssistant()

# Process user instruction
@app.post("/api/generate-steps")
async def generate_steps(request):
    instruction = request.body.instruction
    result = assistant.process_instruction(instruction)
    
    # Check validation
    if result['validation']['is_valid']:
        if result['validation']['confidence'] > 0.7:
            return {"status": "ok", "steps": result['steps']}
        else:
            return {"status": "warning", "steps": result['steps'], 
                   "confidence": result['validation']['confidence']}
    else:
        return {"status": "error", "issues": result['validation']['issues']}
```

## Next Steps

1. **Test with your instructions**: Try validation on real use cases
2. **Review confidence scores**: Understand which instruction types match well
3. **Expand dataset**: Add more examples for better matching
4. **Monitor quality**: Track validation metrics over time
5. **Integrate**: Add validation to your production pipeline

## Support

For issues or questions:
1. Check [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) for detailed docs
2. Review [validate_steps.py](validate_steps.py) for usage examples
3. Run `python validate_steps.py --help` for command options
4. Check logs for detailed error messages

## Summary

✅ **Automatic validation** against your JSONL datasets  
✅ **Confidence scoring** to assess step quality  
✅ **Format checking** to ensure valid structure  
✅ **Dataset matching** to find similar examples  
✅ **Category-specific** validation rules  
✅ **Detailed reporting** with issues and warnings  
✅ **Easy integration** into existing systems  

The validation system ensures high-quality step generation for reliable task automation!
