#!/usr/bin/env python
"""
interactive_validator.py - Interactive validation tool for user-entered instructions
Validates generated steps according to corrected validation criteria
"""

import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from demo import SimpleAssistant, generate_validation_report

def print_header(text, char="="):
    """Print a formatted header"""
    width = 70
    print("\n" + char * width)
    print(text.center(width))
    print(char * width)

def print_step_details(steps):
    """Print detailed step information"""
    if not steps:
        print("  ❌ No steps generated")
        return
    
    print(f"\n📋 GENERATED STEPS ({len(steps)} total):")
    for step in steps:
        step_num = step.get('step', '?')
        action = step.get('action', '[No action]')
        word_count = len(action.split())
        print(f"\n  Step {step_num}:")
        print(f"    Action: {action}")
        print(f"    Words: {word_count}")

def print_validation_report(report):
    """Print validation report in user-friendly format"""
    val = report['validation_details']
    
    print_header("VALIDATION RESULT", "=")
    
    print(f"\n📊 OVERALL STATUS")
    status = "✓ VALID" if val['is_valid'] else "✗ INVALID"
    print(f"  Status: {status}")
    print(f"  Confidence: {val['confidence']:.1%}")
    format_valid = val.get('format_valid', True)
    print(f"  Format Valid: {'✓ Yes' if format_valid else '✗ No'}")
    
    print(f"\n📈 SCORES")
    print(f"  Dataset Match: {val.get('dataset_match_score', 0):.1%}")
    print(f"  Structure: {val.get('structure_score', 0):.1%}")
    print(f"  Content: {val.get('content_score', 0):.1%}")
    
    print(f"\n📂 DATASET INFO")
    stats = val.get('dataset_stats', {})
    print(f"  Category: {report['category']}")
    print(f"  Dataset Entries: {stats.get('total_entries', 'N/A')}")
    print(f"  Average Steps: {stats.get('avg_steps', 0):.1f}")
    
    if val['issues']:
        print(f"\n❌ ISSUES ({len(val['issues'])} found)")
        for issue in val['issues']:
            print(f"  • {issue}")
    else:
        print(f"\n✓ No format issues found")
    
    warnings = val.get('warnings', [])
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)} found)")
        for warning in warnings:
            print(f"  • {warning}")
    
    suggestions = val.get('suggestions', [])
    if suggestions:
        print(f"\n💡 SUGGESTIONS ({len(suggestions)} found)")
        for suggestion in suggestions:
            print(f"  • {suggestion}")
    
    print(f"\n🎯 RECOMMENDATION")
    print(f"  {report['recommendation']}")

def validate_instruction(instruction):
    """Validate a single instruction and its generated steps"""
    print_header(f"VALIDATING: {instruction}", "-")
    
    # Generate validation report
    report = generate_validation_report(instruction)
    
    # Print steps
    print_step_details(report['steps'])
    
    # Print validation results
    print_validation_report(report)
    
    # Return validation result
    is_valid = report['validation_details']['is_valid']
    confidence = report['validation_details']['confidence']
    
    return {
        'is_valid': is_valid,
        'confidence': confidence,
        'steps': report['steps'],
        'issues': report['validation_details'].get('issues', []),
        'warnings': report['validation_details'].get('warnings', []),
        'suggestions': report['validation_details'].get('suggestions', [])
    }

def interactive_mode():
    """Run interactive validation loop"""
    print_header("STEP VALIDATION TOOL", "=")
    print("\n📝 Enter instructions to validate generated steps")
    print("   Type 'quit' or 'exit' to quit\n")
    
    while True:
        try:
            instruction = input("Enter instruction: ").strip()
            
            if instruction.lower() in ['quit', 'exit', 'q']:
                print("\n✓ Thank you for using the validator!")
                break
            
            if not instruction:
                print("⚠️  Please enter a non-empty instruction\n")
                continue
            
            # Validate
            result = validate_instruction(instruction)
            
            # Summary
            print(f"\n📊 VALIDATION SUMMARY")
            print(f"  Valid: {'✓ YES' if result['is_valid'] else '✗ NO'}")
            print(f"  Confidence: {result['confidence']:.1%}")
            print(f"  Issues: {len(result['issues'])}")
            print(f"  Warnings: {len(result['warnings'])}")
            
            # Ask if want to continue
            print("\n" + "-" * 70)
            
        except KeyboardInterrupt:
            print("\n\n✓ Validation interrupted")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("   Please try again or enter a different instruction\n")

def batch_validate(instructions):
    """Validate multiple instructions in batch mode"""
    print_header("BATCH VALIDATION", "=")
    
    results = []
    valid_count = 0
    
    for i, instruction in enumerate(instructions, 1):
        print(f"\n[{i}/{len(instructions)}] Validating: {instruction}")
        
        try:
            result = validate_instruction(instruction)
            results.append({
                'instruction': instruction,
                'result': result
            })
            
            if result['is_valid']:
                valid_count += 1
                status = "✓"
            else:
                status = "✗"
            
            print(f"\n  {status} Confidence: {result['confidence']:.1%}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({
                'instruction': instruction,
                'error': str(e)
            })
    
    # Summary
    print_header("BATCH SUMMARY", "=")
    print(f"\nTotal Instructions: {len(instructions)}")
    print(f"Valid: {valid_count}/{len(instructions)} ({100*valid_count/len(instructions):.0f}%)")
    print(f"Invalid: {len(instructions) - valid_count}/{len(instructions)}")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--batch":
            # Batch mode with instructions from command line
            instructions = sys.argv[2:] if len(sys.argv) > 2 else []
            if instructions:
                batch_validate(instructions)
            else:
                print("Usage: python interactive_validator.py --batch 'Instruction 1' 'Instruction 2'")
        elif sys.argv[1] == "--file":
            # Batch mode from file (one instruction per line)
            if len(sys.argv) < 3:
                print("Usage: python interactive_validator.py --file <filename>")
            else:
                try:
                    with open(sys.argv[2], 'r') as f:
                        instructions = [line.strip() for line in f if line.strip()]
                    batch_validate(instructions)
                except FileNotFoundError:
                    print(f"❌ File not found: {sys.argv[2]}")
        elif sys.argv[1] == "--single":
            # Single instruction mode
            if len(sys.argv) < 3:
                print("Usage: python interactive_validator.py --single 'Your instruction'")
            else:
                instruction = sys.argv[2]
                result = validate_instruction(instruction)
                sys.exit(0 if result['is_valid'] else 1)
        elif sys.argv[1] in ["--help", "-h", "help"]:
            print("""
INTERACTIVE VALIDATOR - Usage Guide
====================================

Mode 1: Interactive (Default)
  python interactive_validator.py
  → Prompts for instructions one at a time

Mode 2: Single Instruction
  python interactive_validator.py --single "Create a JS app to add 2 numbers"
  → Validates one instruction and exits

Mode 3: Batch from Command Line
  python interactive_validator.py --batch "Instr 1" "Instr 2" "Instr 3"
  → Validates multiple instructions from arguments

Mode 4: Batch from File
  python interactive_validator.py --file instructions.txt
  → Validates instructions from file (one per line)

Validation Criteria (Corrected):
  ✓ Format: steps must be dict list with 'step' and 'action' keys
  ✓ Content: each step must have ≥2 words
  ✓ Structure: steps numbered 1, 2, 3... in sequence
  ✓ Length: matches dataset norms (±2 std deviations)
  ✓ Dataset: matched against known examples

Removed Unsuitable Checks:
  ✗ Capital letter requirement (non-essential)
  ✗ Redundant "too brief" check (conflicted with word count)
  ✗ Character-based length (changed to word-based)

Examples:
  python interactive_validator.py
  python interactive_validator.py --single "Play 2048: swipe left"
  python interactive_validator.py --batch "Instr A" "Instr B"
  python interactive_validator.py --file my_instructions.txt
            """)
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage guide")
    else:
        # Default: interactive mode
        interactive_mode()
