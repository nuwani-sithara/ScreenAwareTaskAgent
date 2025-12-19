#!/usr/bin/env python
"""
validate_steps.py - Standalone validation script
Run this to validate steps for specific instructions
"""

import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from demo import SimpleAssistant, StepValidator, generate_validation_report

def validate_single_instruction(instruction):
    """Validate a single instruction"""
    print("\n" + "="*70)
    print("STEP VALIDATION REPORT")
    print("="*70)
    
    report = generate_validation_report(instruction)
    
    print(f"\n📋 INSTRUCTION")
    print(f"  Input: {report['instruction']}")
    print(f"  Category: {report['category']}")
    
    print(f"\n🔄 GENERATED STEPS ({len(report['steps'])} total)")
    for step in report['steps']:
        print(f"  {step['step']}. {step['action']}")
    
    val = report['validation_details']
    
    print(f"\n📊 VALIDATION METRICS")
    print(f"  Status: {'✓ VALID' if val['is_valid'] else '✗ INVALID'}")
    print(f"  Confidence: {val['confidence']:.1%}")
    print(f"  Similarity: {val['similarity']:.1%}")
    print(f"  Format Valid: {'✓ Yes' if val['format_valid'] else '✗ No'}")
    
    if val['matched_instruction']:
        print(f"\n🎯 MATCHED INSTRUCTION (from dataset)")
        print(f"  {val['matched_instruction']}")
    
    if val['issues']:
        print(f"\n❌ ISSUES FOUND")
        for issue in val['issues']:
            print(f"  • {issue}")
    
    if val['warnings']:
        print(f"\n⚠️  WARNINGS")
        for warning in val['warnings']:
            print(f"  • {warning}")
    
    print(f"\n💡 RECOMMENDATION")
    print(f"  {report['recommendation']}")
    
    print("\n" + "="*70)
    
    return report

def validate_multiple(instructions):
    """Validate multiple instructions"""
    print("\n" + "="*70)
    print("BATCH VALIDATION REPORT")
    print("="*70)
    
    results = []
    valid_count = 0
    
    for i, instruction in enumerate(instructions, 1):
        report = generate_validation_report(instruction)
        results.append(report)
        
        if report['validation_details']['is_valid']:
            valid_count += 1
        
        status = "✓" if report['validation_details']['is_valid'] else "✗"
        conf = report['validation_details']['confidence']
        print(f"\n{i}. {status} {instruction}")
        print(f"   Confidence: {conf:.1%}")
    
    print(f"\n\n{'='*70}")
    print(f"SUMMARY: {valid_count}/{len(instructions)} passed ({100*valid_count/len(instructions):.0f}%)")
    print(f"{'='*70}\n")
    
    return results

if __name__ == "__main__":
    # Default test instructions
    default_instructions = [
        "Create a JS app to add 2 numbers",
        "Play 2048 game: swipe left",
        "Create a JS script to validate form input",
        "Play 2048 game: swipe right",
        "Create a Python calculator to multiply numbers",
        "Some random instruction that won't match",  # This will have low confidence
    ]
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--single":
            # Single instruction mode
            if len(sys.argv) < 3:
                print("Usage: python validate_steps.py --single '<instruction>'")
                sys.exit(1)
            instruction = sys.argv[2]
            validate_single_instruction(instruction)
        elif sys.argv[1] == "--batch":
            # Batch mode with custom instructions
            instructions = sys.argv[2:] if len(sys.argv) > 2 else default_instructions
            validate_multiple(instructions)
        elif sys.argv[1] == "--help":
            print("""
Validation Script - Usage Guide
================================

Validate a single instruction:
  python validate_steps.py --single "Create a JS app to add 2 numbers"

Validate multiple instructions:
  python validate_steps.py --batch "Instruction 1" "Instruction 2" "Instruction 3"

Validate with default instructions:
  python validate_steps.py --batch

Show this help:
  python validate_steps.py --help
            """)
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage guide")
    else:
        # Default: validate with default instructions
        validate_multiple(default_instructions)
