"""Quick test of Flan-T5 model"""
from generate_local_model import LocalStepGenerator

# Test cases
test_cases = [
    "Login to Gmail with username test@gmail.com and password Test123",
    "Search for laptop on Amazon and add the first result to cart",
    "Create a new folder named Documents on desktop"
]

print("Testing Flan-T5 Step Generator\n")
generator = LocalStepGenerator()

for i, instruction in enumerate(test_cases, 1):
    print(f"\n{'='*60}")
    print(f"Test {i}: {instruction}")
    print('='*60)
    
    steps = generator.generate_steps(instruction)
    print("\nGenerated Steps:")
    print(steps)
    print()
