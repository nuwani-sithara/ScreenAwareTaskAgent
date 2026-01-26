"""
Quick test to verify your LLM training is working correctly
"""
import json
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

def test_trained_model():
    print("🧪 Testing Your Trained Model\n" + "="*50)
    
    # Load your fine-tuned model
    model_path = "./fine_tuned_js_model/checkpoint-3"
    
    try:
        print(f"📂 Loading model from: {model_path}")
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
        print("✅ Model loaded successfully!\n")
        
        # Test cases from your dataset
        test_instructions = [
            "Create a JS app to add 2 numbers",
            "Create a JS app to subtract 2 numbers",
            "Create a JS app for a simple calculator"
        ]
        
        print("🎯 Testing Model Predictions:\n")
        
        for idx, instruction in enumerate(test_instructions, 1):
            print(f"\n{idx}. Input: {instruction}")
            
            # Tokenize input
            inputs = tokenizer(instruction, return_tensors="pt", max_length=512, truncation=True)
            
            # Generate output
            outputs = model.generate(**inputs, max_length=256, num_beams=4, early_stopping=True)
            
            # Decode output
            prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            print(f"   Output: {prediction}")
            print("-" * 50)
        
        print("\n✅ Training verification complete!")
        print("Your model is working correctly if the outputs look like step-by-step instructions.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check if checkpoint-3 exists in fine_tuned_js_model/")
        print("2. Verify all model files are present")
        print("3. Make sure transformers library is installed")

if __name__ == "__main__":
    test_trained_model()
