"""
Mock demonstration of validation feature without requiring Ollama
Shows what the validation logic does
"""

from typing import Dict, Any, List


class MockValidationDemo:
    """Demonstrates validation logic without LLM calls"""
    
    def validate_instruction_mock(
        self, 
        instruction: str, 
        visual_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulates what the LLM validation does:
        1. Extracts elements from visual data
        2. Checks if instruction mentions elements that exist
        3. Returns validation result
        """
        
        # Extract screen elements
        elements = []
        if "session_data" in visual_data:
            screens = visual_data["session_data"].get("screens", [])
            if screens:
                elements = screens[0].get("elements", [])
        
        # Get element labels/types
        element_texts = []
        for elem in elements:
            label = elem.get("label", "").lower()
            elem_type = elem.get("type", "").lower()
            element_texts.append(label)
            element_texts.append(elem_type)
        
        print(f"\n📺 Screen Elements Found: {element_texts}")
        print(f"📝 Instruction: {instruction}")
        
        # Simple keyword matching (what LLM does semantically)
        instruction_lower = instruction.lower()
        
        # Check for common UI elements mentioned in instruction
        required_elements = []
        if "login" in instruction_lower:
            required_elements.append("login")
        if "username" in instruction_lower:
            required_elements.append("username")
        if "password" in instruction_lower:
            required_elements.append("password")
        if "submit" in instruction_lower or "send" in instruction_lower:
            required_elements.append("submit")
        
        print(f"🔍 Looking for: {required_elements}")
        
        # Check if required elements are on screen
        missing = []
        for required in required_elements:
            found = any(required in text for text in element_texts)
            if not found:
                missing.append(required)
        
        is_valid = len(missing) == 0
        confidence = 1.0 if is_valid else 0.9
        
        # Suggest actions based on what's missing
        suggested_actions = []
        if not is_valid:
            if missing:
                suggested_actions = ["scroll_down", "wait_for_load"]
        
        result = {
            "is_valid": is_valid,
            "confidence": confidence,
            "reason": f"All elements found" if is_valid else f"Missing: {', '.join(missing)}",
            "missing_elements": missing,
            "suggested_actions": suggested_actions
        }
        
        return result


def demo_test_1_match():
    """Test 1: Instruction MATCHES screen elements"""
    print("\n" + "="*70)
    print("TEST 1: MATCHING Instruction (Should PASS)")
    print("="*70)
    
    visual_data = {
        "session_data": {
            "screens": [{
                "elements": [
                    {
                        "type": "input_field",
                        "label": "Username",
                        "x": 863,
                        "y": 475
                    },
                    {
                        "type": "button",
                        "label": "Login",
                        "x": 912,
                        "y": 739
                    }
                ]
            }]
        }
    }
    
    instruction = "Click the Login button"
    
    validator = MockValidationDemo()
    result = validator.validate_instruction_mock(instruction, visual_data)
    
    print(f"\n✅ Validation Result:")
    print(f"   is_valid: {result['is_valid']}")
    print(f"   confidence: {result['confidence']}")
    print(f"   reason: {result['reason']}")
    print(f"   missing: {result['missing_elements']}")
    
    if result['is_valid']:
        print(f"\n✅ TEST 1 PASSED - Validation correctly identified matching elements")
    else:
        print(f"\n❌ TEST 1 FAILED - Should have validated as true")


def demo_test_2_mismatch():
    """Test 2: Instruction DOES NOT MATCH screen elements"""
    print("\n\n" + "="*70)
    print("TEST 2: MISMATCHING Instruction (Should FAIL)")
    print("="*70)
    
    visual_data = {
        "session_data": {
            "screens": [{
                "elements": [
                    {
                        "type": "button",
                        "label": "Logout",
                        "x": 1800,
                        "y": 50
                    },
                    {
                        "type": "text",
                        "label": "Welcome Dashboard",
                        "x": 500,
                        "y": 100
                    }
                ]
            }]
        }
    }
    
    instruction = "Click the Login button and enter username"
    
    validator = MockValidationDemo()
    result = validator.validate_instruction_mock(instruction, visual_data)
    
    print(f"\n⚠️ Validation Result:")
    print(f"   is_valid: {result['is_valid']}")
    print(f"   confidence: {result['confidence']}")
    print(f"   reason: {result['reason']}")
    print(f"   missing: {result['missing_elements']}")
    print(f"   suggested_actions: {result['suggested_actions']}")
    
    if not result['is_valid']:
        print(f"\n✅ TEST 2 PASSED - Validation correctly detected missing elements")
        print(f"   💡 Suggested actions: {result['suggested_actions']}")
    else:
        print(f"\n❌ TEST 2 FAILED - Should have validated as false")


def show_code_explanation():
    """Explain what the real validation code does"""
    print("\n\n" + "="*70)
    print("HOW THE REAL VALIDATION WORKS")
    print("="*70)
    
    print("""
The real validation in hid_step_generator.py does this:

1. EXTRACT VISUAL CONTEXT:
   - Parses screen elements from visual_data
   - Builds text description of all interactive elements
   - Includes element types, labels, and positions

2. LLM VALIDATION PROMPT:
   Sends to Mistral LLM:
   "You have these screen elements: [list]
    User wants to: [instruction]
    Can the instruction be completed? 
    What's missing? What should user do?"

3. PARSE LLM RESPONSE:
   - is_valid: true/false
   - confidence: 0.0-1.0
   - missing_elements: [list of missing items]
   - suggested_actions: ["scroll_down", "wait_for_load", etc.]

4. DECISION LOGIC:
   if (not is_valid AND confidence >= 0.7):
       return VALIDATION_FAILED status
       include suggested_actions
   else:
       proceed with HID command generation

5. RESPONSE:
   {
     "status": "validation_failed",
     "message": "Required elements not found",
     "suggested_actions": ["scroll_down"],
     "missing_elements": ["Login button"],
     "hid_commands": []  // No commands generated
   }
""")


if __name__ == "__main__":
    print("\n🧪 MOCK VALIDATION DEMONSTRATION")
    print("(This simulates what the LLM validation does)")
    
    demo_test_1_match()
    demo_test_2_mismatch()
    show_code_explanation()
    
    print("\n\n" + "="*70)
    print("✅ VALIDATION FEATURE SUMMARY")
    print("="*70)
    print("""
WHAT IT DOES:
- Checks if user instruction matches visible screen elements
- Uses LLM to semantically understand intent vs available UI
- Suggests navigation actions when elements are missing

BENEFITS:
- Prevents errors from clicking non-existent buttons
- Guides user with "scroll_down" when login form is off-screen
- Improves automation reliability

HOW TO USE:
1. Keep skip_validation=False (default)
2. If status=="validation_failed", check suggested_actions
3. Execute suggested action (scroll, wait), capture new screen
4. Retry with new visual_data

DEMONSTRATION ABOVE:
✅ Test 1: Login button on screen + "Click Login" → PASSES
⚠️  Test 2: Dashboard shown + "Click Login" → FAILS (Login not found)
   → Suggests: scroll_down, wait_for_load
""")
    
    print("\n📝 THE FEATURE IS IMPLEMENTED IN:")
    print("   - llm/hid_step_generator.py: validate_instruction_with_visual_context()")
    print("   - llm/api.py: skip_validation parameter")
    print("   - See: llm/VALIDATION_FEATURE.md for full documentation")
    print("\n")
