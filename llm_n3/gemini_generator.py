##gemini_generator.py


from google import genai
from google.genai import types

# Configure API key
GEMINI_API_KEY = "AIzaSyCrsfAxlOVPBJCwYocLgEgc8mo9ySrC7Qk"
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_steps(instruction):
    """Generate automation steps using Google Gemini"""
    
    # Build prompt with examples from dataset
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
    
    try:
        # Generate content using new API
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        # Extract text
        if response.text:
            # Clean up the response
            steps = response.text.strip()
            
            # Format as "Steps:\n1. ..."
            if not steps.startswith("Steps:"):
                if steps.startswith("1."):
                    steps = "Steps:\n" + steps
                else:
                    steps = "Steps:\n1. " + steps
                
            return steps
        else:
            return "Error: No response generated"
            
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Test with various instructions
    test_instructions = [
        "login with username and password",
        "register user with email and password",
        "add product to shopping cart",
        "search for items",
        "update user profile",
    ]
    
    print("=" * 80)
    print("TESTING GOOGLE GEMINI API")
    print("=" * 80)
    
    for instruction in test_instructions:
        print(f"\n📝 Instruction: {instruction}")
        print("-" * 80)
        steps = generate_steps(instruction)
        print(steps)
        print()
