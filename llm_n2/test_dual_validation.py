"""
Complete validation test: Basic + Advanced
Shows both validation layers working together
"""
from generate_local_model import LocalStepGenerator
from validate_generated_steps import validate_steps
from advanced_validation import advanced_validate

print("Loading Flan-T5 model...")
generator = LocalStepGenerator()

test_cases = [
    "Login to Gmail with username test@gmail.com and password Test123",
    "Search for laptop on Amazon and add to cart",
]

print("\n" + "="*70)
print("DUAL-LAYER VALIDATION DEMONSTRATION")
print("="*70)
print("\nLayer 1: Basic Validation (format, numbering, action verbs)")
print("Layer 2: Advanced Validation (workflow, completeness, semantics)")
print("="*70)

for i, instruction in enumerate(test_cases, 1):
    print(f"\n\n{'#'*70}")
    print(f"TEST {i}: {instruction}")
    print(f"{'#'*70}")
    
    # Generate steps
    print("\n🔄 Generating steps...")
    steps = generator.generate_steps(instruction)
    
    print("\n📝 Generated Steps:")
    print("-" * 70)
    print(steps)
    print("-" * 70)
    
    # Layer 1: Basic validation
    print("\n" + "="*70)
    print("LAYER 1: BASIC VALIDATION")
    print("="*70)
    basic_result = validate_steps(steps, instruction, verbose=False)
    
    status = "✅ PASS" if basic_result['is_valid'] else "❌ FAIL"
    print(f"{status} | Score: {basic_result['score']:.0%} | Steps: {basic_result['step_count']}")
    
    if basic_result['issues']:
        print("\n❌ Critical Issues:")
        for issue in basic_result['issues']:
            print(f"  • {issue}")
    
    if basic_result['warnings']:
        print(f"\n⚠️  Warnings:")
        for warning in basic_result['warnings'][:3]:
            print(f"  • {warning}")
    
    # Layer 2: Advanced validation
    print("\n" + "="*70)
    print("LAYER 2: ADVANCED VALIDATION")
    print("="*70)
    advanced_result = advanced_validate(steps, instruction, verbose=False)
    
    print(f"\n📊 Overall Score: {advanced_result['overall_score']:.1%}")
    print("\n🔍 Check Results:")
    
    for check_name, check_result in advanced_result['checks'].items():
        score = check_result['score']
        icon = "✅" if score >= 0.7 else "⚠️" if score >= 0.5 else "❌"
        print(f"  {icon} {check_name.replace('_', ' ').title()}: {score:.0%}")
        
        if check_result['issues']:
            for issue in check_result['issues'][:1]:  # Show first issue
                print(f"     → {issue}")
    
    if advanced_result['insights']:
        print(f"\n💡 Insights:")
        for insight in advanced_result['insights']:
            print(f"  {insight}")
    
    # Combined verdict
    print("\n" + "="*70)
    print("COMBINED VERDICT")
    print("="*70)
    
    overall_pass = basic_result['is_valid'] and advanced_result['overall_score'] >= 0.7
    verdict_icon = "✅" if overall_pass else "⚠️" if advanced_result['overall_score'] >= 0.5 else "❌"
    
    print(f"\n{verdict_icon} Final Status: {'EXCELLENT' if overall_pass else 'NEEDS IMPROVEMENT'}")
    print(f"   Basic Layer: {basic_result['score']:.0%}")
    print(f"   Advanced Layer: {advanced_result['overall_score']:.0%}")
    
    if overall_pass:
        print("\n✨ Steps are high quality and ready to use!")
    else:
        print("\n🔧 Recommendation: Adjust prompt or regenerate for better quality")

print("\n\n" + "="*70)
print("Validation Complete!")
print("="*70)
print("\nValidation Layers Summary:")
print("  Layer 1 (Basic): Format, numbering, action verbs, duplicates")
print("  Layer 2 (Advanced): Workflow logic, completeness, specificity,")
print("                      action coverage, semantic coherence")
print("="*70 + "\n")
