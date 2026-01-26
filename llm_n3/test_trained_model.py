"""Simple test script for trained llm_n model"""
import os

# Check if model exists
model_path = "./models/t5_automation/best"

if not os.path.exists(model_path):
    print("❌ TRAINED MODEL NOT FOUND!")
    print(f"   Expected location: {model_path}")
    print("\n💡 You need to train the model first:")
    print("   python train_t5_automation.py")
    exit(1)

print("✅ Model found! Loading...")

try:
    from transformers import T5Tokenizer, T5ForConditionalGeneration
    import torch
    
    # Load model
    tokenizer = T5Tokenizer.from_pretrained(model_path)
    model = T5ForConditionalGeneration.from_pretrained(model_path)
    model.eval()
    
    print("✅ Model loaded successfully!\n")
    
    # Test instructions
    test_cases = [
        "login with username and password",
        "search for a product",
        "add item to cart",
        "download a file",
        "send an email",
        "Create a JS app to add 2 numbers",
    ]
    
    print("🧪 TESTING STEP GENERATION")
    print("="*70)
    
    for instruction in test_cases:
        print(f"\n📝 Instruction: {instruction}")
        print("-" * 70)
        
        # Format for T5
        input_text = f"generate automation steps: {instruction}"
        
        # Tokenize
        inputs = tokenizer(input_text, return_tensors="pt", max_length=128, truncation=True)
        
        # Generate
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_length=256,
                num_beams=4,
                early_stopping=True,
                no_repeat_ngram_size=2
            )
        
        # Decode
        result = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        print(f"Generated Steps:")
        print(f"  {result}")
        
        # Quality check
        step_count = result.count("Step")
        has_proper_format = "Step 1:" in result or "Step 2:" in result
        
        if step_count >= 3 and has_proper_format:
            print(f"Quality: ✅ Good ({step_count} steps)")
        else:
            print(f"Quality: ⚠️  Needs improvement ({step_count} steps)")
    
    print("\n" + "="*70)
    print("✅ Testing complete!")
    print("\n💡 If quality is poor, consider:")
    print("   1. Training for more epochs")
    print("   2. Merging datasets (use merge_datasets.py)")
    print("   3. Adjusting training parameters")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nMake sure you have:")
    print("  - transformers installed: pip install transformers")
    print("  - torch installed: pip install torch")
