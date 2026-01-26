#!/usr/bin/env python
"""
validate_from_demo.py - Wrapper script to validate instructions entered by user
This script integrates with demo.py to automatically validate instructions without 
switching to interactive_validator.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from demo import SimpleAssistant

def print_header(text, char="="):
    """Print formatted header"""
    width = 70
    print("\n" + char * width)
    print(text.center(width))
    print(char * width)

def validate_and_display(instruction=None, result=None):
    """Process instruction and display validation results.

    If `result` is provided, use it directly and skip re-processing the
    instruction to avoid duplicate outputs written by `demo.SimpleAssistant`.
    """
    if instruction is None and result is None:
        print("❌ validate_and_display requires an instruction or a result object")
        return False

    header_text = instruction if instruction is not None else result.get('instruction', 'provided result')
    print_header(f"VALIDATING: {header_text}", "-")

    try:
        # Use the provided result when available to avoid double-processing
        if result is None:
            assistant = SimpleAssistant()
            result = assistant.process_instruction(instruction)
        
        # Extract validation details
        val = result['validation']
        steps = result['steps']
        category = result['category']
        
        # Print generated steps
        print(f"\n📋 GENERATED STEPS ({len(steps)} total):")
        if steps:
            for step in steps:
                step_num = step.get('step', '?')
                action = step.get('action', '[No action]')
                word_count = len(action.split()) if action else 0
                print(f"   Step {step_num}: {action}")
                print(f"      Words: {word_count}")
        else:
            print("   ❌ No steps generated")
        
        # Print validation summary
        print_header("VALIDATION RESULT", "=")
        
        print(f"\n📊 OVERALL STATUS")
        status = "✓ VALID" if val['is_valid'] else "✗ INVALID"
        print(f"  Status: {status}")
        print(f"  Confidence: {val['confidence']:.1%}")
        print(f"  Format Valid: {'✓ Yes' if val.get('format_valid', True) else '✗ No'}")
        
        print(f"\n📈 SCORES")
        print(f"  Dataset Match: {val.get('dataset_match_score', 0):.1%}")
        print(f"  Structure: {val.get('structure_score', 0):.1%}")
        print(f"  Content: {val.get('content_score', 0):.1%}")
        
        print(f"\n📂 DATASET INFO")
        print(f"  Category: {category}")
        stats = val.get('dataset_stats', {})
        print(f"  Dataset Entries: {stats.get('total_entries', 'N/A')}")
        print(f"  Average Steps: {stats.get('avg_steps', 0):.1f}")
        
        if val.get('issues'):
            print(f"\n❌ ISSUES ({len(val['issues'])} found)")
            for issue in val['issues']:
                print(f"  • {issue}")
        else:
            print(f"\n✓ No format issues found")
        
        if val.get('warnings'):
            print(f"\n⚠️  WARNINGS ({len(val['warnings'])} found)")
            for warning in val['warnings']:
                print(f"  • {warning}")
        
        if val.get('suggestions'):
            print(f"\n💡 SUGGESTIONS ({len(val['suggestions'])} found)")
            for suggestion in val['suggestions']:
                print(f"  • {suggestion}")
        
        # Recommendation
        print(f"\n🎯 RECOMMENDATION")
        if val['is_valid'] and val['confidence'] > 0.8:
            rec = "✓ Steps are valid and ready for execution"
        elif val['is_valid']:
            rec = "⚠️  Steps are valid but confidence is moderate. Review before execution."
        elif val.get('issues'):
            rec = "✗ Steps have issues. Review and regenerate if needed."
        else:
            rec = "⚠️  Steps have warnings. Consider reviewing for improvements."
        print(f"  {rec}")
        
        return val['is_valid']
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def interactive_mode():
    """Run interactive validation loop"""
    print_header("STEP VALIDATOR - DEMO.PY INTEGRATION", "=")
    print("\n📝 Enter instructions to automatically generate and validate steps")
    print("   Type 'quit' or 'exit' to quit\n")
    
    while True:
        try:
            instruction = input("📌 Enter instruction: ").strip()
            
            if instruction.lower() in ['quit', 'exit', 'q']:
                print("\n✓ Thank you for using the validator!")
                break
            
            if not instruction:
                print("⚠️  Please enter a non-empty instruction\n")
                continue
            
            # Validate and display
            is_valid = validate_and_display(instruction)
            
            # Summary
            print(f"\n{'='*70}")
            print(f"Result: {'✓ VALID' if is_valid else '✗ INVALID'}")
            print(f"{'='*70}\n")
            
        except KeyboardInterrupt:
            print("\n\n✓ Validation interrupted")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("   Please try again\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--single":
            # Single instruction mode
            if len(sys.argv) < 3:
                print("Usage: python validate_from_demo.py --single 'Your instruction'")
            else:
                instruction = sys.argv[2]
                is_valid = validate_and_display(instruction)
                sys.exit(0 if is_valid else 1)
        elif sys.argv[1] in ["--help", "-h", "help"]:
            print("""
VALIDATE FROM DEMO - Integrated Validation Tool
===============================================

This tool validates instructions directly from demo.py without
needing to switch to interactive_validator.py

Usage:

Mode 1: Interactive (Default)
  python validate_from_demo.py
  → Prompts for instructions one at a time
  → Shows immediate validation results

Mode 2: Single Instruction
  python validate_from_demo.py --single "Your instruction"
  → Validates one instruction and exits

Examples:
  python validate_from_demo.py
  python validate_from_demo.py --single "Play 2048: swipe left"
  python validate_from_demo.py --single "Create a JS calculator"
            """)
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage guide")
    else:
        # Default: interactive mode
        interactive_mode()
