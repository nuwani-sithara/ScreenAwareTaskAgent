"""
Test Automation Model
Quick test of the trained automation step generator.
"""

from generate import load_model, TextGenerator
import torch

print("Loading trained automation model...")
model, tokenizer, config = load_model('models/checkpoints/best_model.pt')

generator = TextGenerator(model, tokenizer, 'cpu')

# Test prompts
test_instructions = [
    "login with username and password",
    "search for a product",
    "add item to cart",
    "create new account"
]

print("\n" + "="*80)
print("TESTING AUTOMATION STEP GENERATION")
print("="*80)

for instruction in test_instructions:
    # Format prompt the way model was trained
    prompt = f"Instruction: {instruction}\nSteps:"
    
    print(f"\n📝 Instruction: {instruction}")
    print("-" * 80)
    
    # Generate with greedy decoding for consistent output
    text = generator.generate(
        prompt,
        max_length=100,
        temperature=0.3,  # Low temperature for focused output
        top_k=10,         # Very focused
        top_p=0.85,
        repetition_penalty=1.3
    )
    
    # Extract just the steps part
    if "Steps:" in text:
        steps = text.split("Steps:")[1].strip()
        print(f"✅ Generated: {steps[:200]}...")
    else:
        print(f"Output: {text}")
    print()

print("="*80)
print("✓ Testing complete!")
print("\n💡 To use in GUI:")
print("   1. Format prompt as: Instruction: <your instruction>")
print("   2. Add 'Steps:' at the end")
print("   3. Or modify GUI to auto-format")
