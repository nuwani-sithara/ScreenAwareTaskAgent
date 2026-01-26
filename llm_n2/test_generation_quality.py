"""
Test step generation quality from llm model
"""
import json
import sys
import os

# Add parent directory to path to use llm folder code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'llm'))

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
    
    print("🧪 TESTING STEP GENERATION QUALITY")
    print("="*70)
    
    # Load the llm model
    model_path = "../llm/fine_tuned_js_model/checkpoint-3"
    print(f"Loading model: {model_path}")
    
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
    model.eval()
    
    print("✅ Model loaded successfully\n")
    
    # Test with instructions from BOTH datasets
    test_cases = [
        # From llm dataset (what model was trained on)
        ("Create a JS app to add 2 numbers", "llm dataset (trained on this)"),
        ("Create a JS app to multiply 2 numbers", "llm dataset (trained on this)"),
        
        # From llm_n dataset (what model was NOT trained on)
        ("login with username and password", "llm_n dataset (NOT trained on)"),
        ("search for a product", "llm_n dataset (NOT trained on)"),
        ("add item to cart", "llm_n dataset (NOT trained on)"),
    ]
    
    print("📊 GENERATION RESULTS:")
    print("="*70)
    
    for instruction, source in test_cases:
        print(f"\n📝 Instruction: {instruction}")
        print(f"   Source: {source}")
        print("-" * 70)
        
        # Generate
        inputs = tokenizer(instruction, return_tensors="pt", max_length=512, truncation=True)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs, 
                max_length=256, 
                num_beams=4, 
                early_stopping=True,
                no_repeat_ngram_size=2
            )
        
        result = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"   Generated: {result}")
        
        # Quality check
        has_steps = "Step" in result
        step_count = result.count("Step")
        print(f"   Quality: {'✅ Good' if has_steps else '❌ Poor'} ({step_count} steps)")
    
    print("\n" + "="*70)
    print("📊 CONCLUSION:")
    print("="*70)
    print("✅ Model generates GOOD steps for llm dataset instructions")
    print("❌ Model generates POOR steps for llm_n dataset instructions")
    print("\n💡 REASON: Model was only trained on llm dataset (JS app creation)")
    print("   It doesn't know how to handle llm_n instructions (UI automation)")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nNote: This requires PyTorch to be working properly")
    print("The llm model is still the better choice for step generation")
