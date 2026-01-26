##generate_llm_steps_cli.py

"""
Command-line interface for generating automation steps using Gemini API.
Simple terminal-based alternative to the GUI.
"""

from google import genai
import sys


class StepGeneratorCLI:
    """Terminal-based step generator."""
    
    def __init__(self):
        """Initialize Gemini client."""
        GEMINI_API_KEY = "AIzaSyCrsfAxlOVPBJCwYocLgEgc8mo9ySrC7Qk"
        self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        self.models_to_try = ['gemini-2.0-flash', 'gemini-flash-latest', 'gemini-pro-latest']
    
    def generate_steps(self, instruction):
        """Generate automation steps from instruction."""
        # Build prompt
        prompt = f"""You are a human-like UI test automation agent.

Your task is to convert a user's instruction into clear, executable UI test steps.

Rules:
- Generate only UI interaction steps.
- Each step must start with a strong action verb (e.g., Open, Click, Enter, Select, Navigate, Verify).
- Steps must be sequential and logical.
- Do NOT include planning, coding, or implementation steps.
- Do NOT explain — only output the steps.

Format:
Steps:
1. <Step one>
2. <Step two>
3. <Step three>
...

Instruction: {instruction}

Steps:
1."""
        
        # Try each model until one works
        last_error = None
        for model_name in self.models_to_try:
            try:
                print(f"⏳ Generating steps...", end='\r')
                
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                
                if response.text:
                    steps = response.text.strip()
                    
                    # Format output
                    if not steps.startswith("Steps:"):
                        if steps.startswith("1."):
                            steps = "Steps:\n" + steps
                        else:
                            steps = "Steps:\n1. " + steps
                    
                    return steps
                    
            except Exception as e:
                last_error = str(e)
                if '503' in last_error or 'overloaded' in last_error.lower():
                    continue
                continue
        
        return f"❌ Error: All models failed. {last_error}"
    
    def run_interactive(self):
        """Run interactive mode - keep asking for instructions."""
        print("=" * 80)
        print("🤖 GEMINI AUTOMATION STEP GENERATOR - TERMINAL MODE")
        print("=" * 80)
        print("Enter your instruction and get automation steps instantly!")
        print("Commands: 'exit' or 'quit' to stop, 'clear' to clear screen\n")
        
        while True:
            try:
                # Get instruction from user
                instruction = input("\n📝 Instruction: ").strip()
                
                # Handle commands
                if instruction.lower() in ['exit', 'quit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                if instruction.lower() == 'clear':
                    import os
                    os.system('cls' if os.name == 'nt' else 'clear')
                    continue
                
                if not instruction:
                    print("⚠️  Please enter an instruction.")
                    continue
                
                # Generate steps
                print()
                print("-" * 80)
                steps = self.generate_steps(instruction)
                print(" " * 80, end='\r')  # Clear the "Generating..." message
                print(steps)
                print("-" * 80)
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    def run_single(self, instruction):
        """Run single instruction mode."""
        print("=" * 80)
        print("🤖 AUTOMATION STEP GENERATOR")
        print("=" * 80)
        print(f"\n📝 Instruction: {instruction}\n")
        
        steps = self.generate_steps(instruction)
        print(" " * 80, end='\r')  # Clear the "Generating..." message
        print(steps)
        print("\n" + "=" * 80)


def main():
    """Main entry point."""
    generator = StepGeneratorCLI()
    
    # Check if instruction was passed as command-line argument
    if len(sys.argv) > 1:
        # Single mode: use command-line argument
        instruction = ' '.join(sys.argv[1:])
        generator.run_single(instruction)
    else:
        # Interactive mode: keep asking for instructions
        generator.run_interactive()


if __name__ == "__main__":
    main()
