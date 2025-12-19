# Step Validation System - User Guide

## Overview
The Step Validator is an integrated validation system that validates steps generated from user instructions against your JSONL dataset files.

## Features

### 1. **Automatic Validation**
- ✓ Validates step format and structure
- ✓ Compares against similar instructions in datasets
- ✓ Calculates similarity scores
- ✓ Provides confidence metrics
- ✓ Detects and reports issues and warnings

### 2. **Validation Metrics**

#### Confidence Score (0-100%)
- **95%+**: Steps match dataset examples closely → Ready for execution
- **70-94%**: Steps are valid with good similarity → Safe to use
- **50-69%**: Steps are valid but differ from examples → Review before use
- **<50%**: Low confidence → Regenerate steps

#### Similarity Score (0-100%)
Compares generated steps with similar examples from your dataset:
- Measures action text similarity
- Compares step counts
- Calculates weighted average score

#### Format Validation
Checks each step for:
- Required fields (`step`, `action`)
- Proper numbering
- Non-empty actions
- Minimum action length (≥5 characters)

### 3. **Validation Results**

Each result includes:
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

## Validation Categories

### General Software Instructions
Validates for typical software development keywords:
- `create`, `implement`, `add`, `set up`
- `button`, `field`, `input`, `output`

### Game 2048 Instructions
Validates for 2048-specific keywords:
- `focus`, `game`, `window`
- Arrow key references, tile operations

## Example Usage

### Interactive Mode with Validation
```python
assistant = SimpleAssistant()
assistant.interactive_mode()
```

When you enter an instruction, you'll see:
```
🎯 Processing: 'Create a JS app to add 2 numbers'
📂 Category: general_software arithmetic_operations
🤖 Using fine-tuned model for general software
✅ VALIDATION RESULTS:
   Status: ✓ VALID
   Confidence: 95.0%
   Similarity: 100.0%
   Matched: 'Create a JS app to add 2 numbers'
```

### Batch Testing with Summary Report
```python
python demo.py --test
```

Outputs:
- Individual validation results for each test case
- Summary report with:
  - Total tests run
  - Pass/fail counts
  - Success rate
  - Detailed results per instruction

### Generate Validation Report
```python
report = generate_validation_report("Create a JS app to add 2 numbers")
```

Returns comprehensive report with:
- Timestamp
- Instruction and category
- Generated steps
- Validation details
- Recommendation

## Understanding Validation Issues

### ❌ Issues (Critical)
These prevent step execution:
- Format errors (missing fields)
- No steps generated
- Significantly different from dataset

### ⚠️ Warnings (Advisory)
These suggest review but don't block execution:
- Step count mismatch
- Missing domain keywords
- Low similarity to examples

## Dataset Files

### llm_dataset.jsonl
- 79 general software examples
- Covers: addition, subtraction, multiplication, division
- JS and Python examples
- Format: `{"instruction": "...", "output": "Step 1: ... Step 2: ..."}`

### rag_2048.jsonl
- 47 game 2048 examples
- Covers: start game, restart, swipe directions
- Format: same as above

## Best Practices

1. **Check Confidence Score**: If <70%, review the steps
2. **Review Warnings**: Warnings indicate suggestions for improvement
3. **Match Dataset Format**: Ensure steps follow "Step N: Action" pattern
4. **Use Fallbacks**: System automatically falls back to dataset examples when needed
5. **Test Categories**: Different categories have different validation rules

## Troubleshooting

### Low Confidence Scores
**Cause**: Steps differ significantly from dataset examples
**Solution**: 
- Review the matched instruction
- Check if the instruction is in your dataset
- Consider adding similar examples to dataset

### Format Validation Failures
**Cause**: Steps don't have required fields or proper structure
**Solution**:
- Ensure each step has `step`, `action`, and `description` fields
- Check that step numbers are sequential (1, 2, 3...)
- Verify action text is not empty

### No Dataset Match
**Cause**: Instruction doesn't match any dataset examples
**Solution**:
- Check if instruction is similar to dataset examples
- Use generic fallback steps
- Improve dataset coverage

## API Reference

### StepValidator Class

```python
validator = StepValidator(general_dataset_path, game_2048_dataset_path)

# Validate steps
result = validator.validate_steps(instruction, steps, category)
```

**Result Fields**:
- `is_valid` (bool): Whether validation passed
- `confidence` (float 0-1): Confidence score
- `matched_instruction` (str): Most similar dataset instruction
- `similarity` (float 0-1): Similarity score
- `issues` (list): Critical issues
- `warnings` (list): Warnings
- `format_valid` (bool): Format passed validation

## Validation Workflow

```
User Instruction
    ↓
Generate Steps (Model/RAG/Fallback)
    ↓
Format Validation ← Check structure
    ↓
Dataset Matching ← Find similar example
    ↓
Similarity Scoring ← Compare with example
    ↓
Confidence Calculation ← Compute overall score
    ↓
Category-Specific Checks ← Validate keywords
    ↓
Generate Validation Report
    ↓
Output Result + Recommendation
```

## Success Criteria

✓ **Steps are valid for execution if**:
- Format validation passes (all required fields present)
- Confidence ≥ 50%
- No critical issues found
- Properly numbered and ordered

## Future Enhancements

- [ ] Custom validation rules per category
- [ ] Machine learning-based quality scoring
- [ ] Validation metrics dashboard
- [ ] Batch validation with CSV export
- [ ] Step regeneration based on validation feedback
