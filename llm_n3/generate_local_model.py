"""
Local Model Step Generator - No API Key Required
Uses Flan-T5 from HuggingFace (instruction-tuned, works offline)
"""
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from validate_generated_steps import validate_steps

class LocalStepGenerator:
    def __init__(self, model_name="google/flan-t5-large"):
        """Initialize with Flan-T5 model (downloads on first run, then cached)"""
        print(f"Loading {model_name}...")
        print("(First run will download ~3GB for flan-t5-large, then cached locally)")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        print(f"✓ Model loaded on {self.device}")
    
    def generate_steps(self, instruction, max_length=512, num_beams=5):
        """Generate automation steps from instruction using Flan-T5"""
        # Improved few-shot prompt with clear breakdown example
        prompt = f"""Convert high-level tasks into detailed UI automation steps. Break down each action into specific clicks, typing, and navigation.

Example:
Task: Login to Facebook with email john@email.com
Breakdown:
1. Open web browser
2. Navigate to www.facebook.com
3. Click on the email input field
4. Type john@email.com
5. Click on the password input field
6. Type the password
7. Click the Login button

Now break down this task:
Task: {instruction}
Breakdown:
1."""
        
        # Tokenize
        inputs = self.tokenizer(
            prompt, 
            return_tensors="pt", 
            max_length=420,
            truncation=True
        ).to(self.device)
        
        # Generate with Flan-T5 optimized parameters
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_length,
                num_beams=num_beams,
                early_stopping=True,
                no_repeat_ngram_size=3,
                length_penalty=2.0,
                min_length=50
            )
        
        # Decode and format
        steps = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Clean up and format steps properly
        import re
        
        # Remove any duplicate "Steps:" or "Breakdown:" labels
        steps = re.sub(r'(Steps:|Breakdown:)\s*', '', steps)
        
        # Normalize numbering formats
        steps = re.sub(r'(\d+)\)\s+', r'\n\1. ', steps)
        steps = re.sub(r'(\d+)\.\s+', r'\n\1. ', steps)
        steps = steps.strip()
        
        # Ensure proper formatting
        if not steps.startswith("1."):
            steps = "1. " + steps
            
        steps = "Steps:\n" + steps
            
        return steps
        
        # Decode
        steps = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return steps

def main():
    """Interactive CLI using Flan-T5"""
    print("=" * 60)
    print("FLAN-T5 STEP GENERATOR (No API Key Required)")
    print("=" * 60)
    print("Using: google/flan-t5-large (instruction-tuned)")
    print("Features: Step generation + validation")
    print()
    
    # Load model
    generator = LocalStepGenerator()
    
    print("\n" + "=" * 60)
    print("Ready! Enter instructions (type 'exit' to quit)")
    print("Type 'validate on' or 'validate off' to toggle validation")
    print("=" * 60)
    print()
    
    validate_enabled = True
    
    while True:
        instruction = input("📝 Enter instruction: ").strip()
        
        if instruction.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
        
        if instruction.lower() == 'validate on':
            validate_enabled = True
            print("✅ Validation enabled")
            continue
        elif instruction.lower() == 'validate off':
            validate_enabled = False
            print("⚠️ Validation disabled")
            continue
        
        if not instruction:
            print("⚠️ Please enter an instruction")
            continue
        
        print("\n🔄 Generating steps...")
        try:
            steps = generator.generate_steps(instruction)
            print("\n✅ Generated Steps:")
            print("-" * 60)
            print(steps)
            print("-" * 60)
            
            # Validate if enabled
            if validate_enabled:
                print("\n🔍 Validating steps...")
                validation = validate_steps(steps, instruction, verbose=False)
                
                status_icon = "✅" if validation['is_valid'] else "❌"
                print(f"\n{status_icon} Validation: {'PASSED' if validation['is_valid'] else 'FAILED'}")
                print(f"   Quality Score: {validation['score']:.1%}")
                print(f"   Steps Count: {validation['step_count']}")
                
                if validation['issues']:
                    print(f"\n   ❌ Issues:")
                    for issue in validation['issues']:
                        print(f"      • {issue}")
                
                if validation['warnings']:
                    print(f"\n   ⚠️  Warnings:")
                    for warning in validation['warnings'][:3]:  # Show first 3
                        print(f"      • {warning}")
                    if len(validation['warnings']) > 3:
                        print(f"      ... and {len(validation['warnings']) - 3} more")
                
                if validation['suggestions']:
                    print(f"\n   💡 Suggestions:")
                    for suggestion in validation['suggestions']:
                        print(f"      • {suggestion}")
            
            print()
        except Exception as e:
            print(f"❌ Error: {e}")
            print()

if __name__ == "__main__":
    main()
