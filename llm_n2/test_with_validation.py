"""Test script: Generate and validate steps"""
from generate_local_model import LocalStepGenerator
from validate_generated_steps import validate_steps

# Initialize generator
print("Loading model...")
generator = LocalStepGenerator()

# Test cases
test_cases = [
    "Login to Gmail with username test@gmail.com and password Test123",
    "Search for laptop on Amazon and add to cart",
    "Create a new folder named Documents on desktop"
]

print("\n" + "="*70)
print("TESTING: GENERATION + VALIDATION")
print("="*70)

for i, instruction in enumerate(test_cases, 1):
    print(f"\n\n{'#'*70}")
    print(f"TEST {i}: {instruction}")
    print(f"{'#'*70}")
    
    # Generate
    print("\n🔄 Generating steps...")
    steps = generator.generate_steps(instruction)
    
    print("\n📝 Generated Output:")
    print("-" * 70)
    print(steps)
    print("-" * 70)
    
    # Validate
    print("\n🔍 Validating...")
    validation = validate_steps(steps, instruction, verbose=False)
    
    # Show compact results
    status = "✅ PASS" if validation['is_valid'] else "❌ FAIL"
    print(f"\n{status} | Score: {validation['score']:.0%} | Steps: {validation['step_count']}")
    
    if validation['issues']:
        print("\n❌ Issues:")
        for issue in validation['issues']:
            print(f"  • {issue}")
    
    if validation['warnings']:
        print(f"\n⚠️  Warnings ({len(validation['warnings'])}):")
        for warning in validation['warnings'][:2]:
            print(f"  • {warning}")
        if len(validation['warnings']) > 2:
            print(f"  ... and {len(validation['warnings']) - 2} more")

print("\n\n" + "="*70)
print("Testing complete!")
print("="*70)
