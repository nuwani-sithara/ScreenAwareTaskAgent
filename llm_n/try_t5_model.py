"""Use pre-trained T5 model for automation step generation"""
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration

# Load existing fine-tuned T5 model from ../llm folder
model_path = "../llm/fine_tuned_js_model/checkpoint-3"

print("Loading T5 model...")
tokenizer = T5Tokenizer.from_pretrained(model_path)
model = T5ForConditionalGeneration.from_pretrained(model_path)
model.eval()

print("✓ Model loaded\n")

# Test instructions
instructions = [
    "login with username and password",
    "search for a product",
    "download a file",
    "send an email",
]

print("="*80)
print("TESTING T5 MODEL FOR AUTOMATION")
print("="*80)

for instruction in instructions:
    # Format as task for T5
    input_text = f"generate automation steps: {instruction}"
    
    print(f"\n📝 Instruction: {instruction}")
    print("-" * 80)
    
    # Tokenize
    inputs = tokenizer(input_text, return_tensors="pt", max_length=128, truncation=True)
    
    # Generate
    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_length=200,
            num_beams=5,
            temperature=0.7,
            do_sample=True,
            top_p=0.9,
            no_repeat_ngram_size=2
        )
    
    # Decode
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"Generated: {result}")

print("\n" + "="*80)
print("\n💡 This uses the existing fine-tuned T5 model from ../llm folder")
print("   It may work better since it's a larger pre-trained model")
