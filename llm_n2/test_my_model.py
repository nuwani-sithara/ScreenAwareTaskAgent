"""Test your trained model with custom instructions"""
import sys
sys.path.insert(0, 'scripts')
from generate import load_model, TextGenerator

# Load trained model
model, tokenizer, config = load_model('models/checkpoints/best_model.pt', 'cpu')
generator = TextGenerator(model, tokenizer, 'cpu')

# Test your own instructions
instructions = [
    "login with username and password",
    "search for a product",
    "download a file",
    "send an email",
    "create new document",
]

print("="*80)
print("TESTING YOUR TRAINED MODEL")
print("="*80)

for instruction in instructions:
    prompt = f"Instruction: {instruction}\nSteps:"
    
    print(f"\n📝 {instruction}")
    print("-" * 80)
    
    # Generate with moderate temperature for balance
    output = generator.generate(
        prompt,
        max_length=200,
        temperature=0.6,
        top_k=40,
        top_p=0.9,
        repetition_penalty=1.2
    )
    
    # Extract steps
    if "Steps:" in output:
        steps = output.split("Steps:", 1)[1].strip()
        print(steps)
    else:
        print(output)

print("\n" + "="*80)
print("\n💡 To test your own instruction:")
print("   Change the 'instructions' list above and run again")
