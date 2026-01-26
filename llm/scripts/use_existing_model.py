"""
Use Existing Fine-Tuned Model
Load the existing fine-tuned model from llm folder and test it.
"""

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch

print("="*80)
print("LOADING EXISTING FINE-TUNED MODEL")
print("="*80)

model_path = "../llm/fine_tuned_js_model/checkpoint-3"

print(f"\n📁 Loading model from: {model_path}")
print("This may take a moment...\n")

# Load tokenizer and model (T5 is sequence-to-sequence)
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSeq2SeqLM.from_pretrained(model_path)

print("✓ Model loaded successfully!")
print(f"  Parameters: {sum(p.numel() for p in model.parameters()):,}\n")

# Test with sample instructions
test_instructions = [
    "login with username and password",
    "Create a JS app to add 2 numbers",
    "search for a product and add to cart",
]

print("="*80)
print("TESTING GENERATION")
print("="*80)

for instruction in test_instructions:
    print(f"\n📝 Instruction: {instruction}")
    print("-" * 80)
    
    # Tokenize input
    inputs = tokenizer(instruction, return_tensors="pt")
    
    # Generate
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.7,
            top_k=50,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    
    # Decode
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    print(f"✅ Output:\n{generated_text}\n")

print("="*80)
print("\n💡 This model works with Hugging Face transformers.")
print("   To use in the GUI, you have two options:")
print("   1. Modify GUI to use transformers instead of custom model")
print("   2. Copy this functionality to a standalone script")
