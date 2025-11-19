# demo.py - fine-tune + RAG for all
import json
import os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

# ----------------------------
# 1️⃣ Load dataset
# ----------------------------
def load_dataset(file_path="llm_dataset.jsonl"):
    dataset = []
    try:
        with open(file_path, "r") as f:
            for line in f:
                dataset.append(json.loads(line))
    except FileNotFoundError:
        print(f"❌ Dataset file not found: {file_path}")
    return dataset

dataset = load_dataset()
instructions = [entry["instruction"] for entry in dataset]

# ----------------------------
# 2️⃣ Build simple TF-IDF embeddings for retrieval
# ----------------------------
vectorizer = TfidfVectorizer()
dataset_embeddings = vectorizer.fit_transform(instructions)
print(f"✅ Dataset embeddings ready ({len(instructions)} instructions)")

# ----------------------------
# 3️⃣ Load fine-tuned LLM (auto-detect local checkpoint)
# ----------------------------
def find_local_checkpoint(base_dir="fine_tuned_js_model"):
    base_path = os.path.join(os.path.dirname(__file__), base_dir) if '__file__' in globals() else base_dir
    if os.path.isdir(base_path):
        root_files = os.listdir(base_path)
        if any(f in root_files for f in ("config.json", "pytorch_model.bin", "model.safetensors")):
            return base_path
        subdirs = [d for d in root_files if os.path.isdir(os.path.join(base_path, d))]
        checkpoint_dirs = [d for d in subdirs if d.startswith("checkpoint")]
        if checkpoint_dirs:
            def ckpt_key(name):
                nums = ''.join(ch for ch in name if ch.isdigit())
                return int(nums) if nums else 0
            checkpoint_dirs.sort(key=ckpt_key, reverse=True)
            for d in checkpoint_dirs:
                candidate = os.path.join(base_path, d)
                files = os.listdir(candidate)
                if any(f in files for f in ("config.json", "pytorch_model.bin", "model.safetensors")):
                    return candidate
    return None

try:
    model_candidate = find_local_checkpoint("fine_tuned_js_model")
    if model_candidate is None:
        raise FileNotFoundError("No local checkpoint found under 'fine_tuned_js_model'")

    model_name = model_candidate
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    except Exception:
        cfg_path = os.path.join(model_name, "config.json")
        fallback_tokenizer = "t5-small"
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as fh:
                    cfg = json.load(fh)
                    if cfg.get("model_type") == "t5":
                        fallback_tokenizer = "t5-small"
        except Exception:
            pass
        print(f"ℹ️ Tokenizer not found in checkpoint, falling back to '{fallback_tokenizer}' tokenizer")
        tokenizer = AutoTokenizer.from_pretrained(fallback_tokenizer)
        try:
            tokenizer.save_pretrained(model_name)
            print(f"✅ Saved fallback tokenizer files to: {model_name}")
        except Exception as _e:
            print(f"⚠️ Could not save tokenizer to checkpoint: {_e}")

    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, local_files_only=True)
    device = torch.device("cpu")
    model.to(device)
    fine_tuned_available = True
    print(f"✅ Fine-tuned model loaded from: {model_name}")
except Exception as e:
    print(f"⚠️ Fine-tuned model not found or failed: {e}")
    print("ℹ️ Tip: set `model_name` manually or install 'safetensors'.")
    fine_tuned_available = False

# ----------------------------
# 4️⃣ RAG retrieval using cosine similarity
# ----------------------------
def retrieve_similar_instruction(query, top_k=1):
    query_vec = vectorizer.transform([query])
    sims = cosine_similarity(query_vec, dataset_embeddings)[0]
    top_indices = np.argsort(sims)[::-1][:top_k]
    return [dataset[i] for i in top_indices]

# ----------------------------
# 5️⃣ Generate JS steps using RAG + fine-tuned model
# ----------------------------
def generate_js_steps(instruction, top_k=1):
    retrieved = retrieve_similar_instruction(instruction, top_k=top_k)

    # 🔍 DEBUG: SHOW RAG RETRIEVAL
    print("\n🔍 RAG Retrieved Example:")
    if not retrieved:
        print("⚠️ No similar instruction found")
    else:
        for r in retrieved:
            print(json.dumps(r, indent=2))

    if fine_tuned_available and retrieved:
        context = "\n".join([r["output"] for r in retrieved])
        prompt = f"Instruction: {instruction}\nUse the following examples as reference:\n{context}\nGenerate steps:"
        inputs = tokenizer(prompt, return_tensors="pt")
        for k, v in inputs.items():
            inputs[k] = v.to(device)
        with torch.no_grad():
            gen = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        steps_text = tokenizer.decode(gen[0], skip_special_tokens=True)
        steps = []
        for s in steps_text.split("Step ")[1:]:
            try:
                num, rest = s.split(":", 1)
                steps.append({"step": int(num.strip()), "action": rest.strip(), "description": ""})
            except ValueError:
                steps.append({"step": 0, "action": s.strip(), "description": ""})
        return steps

    elif retrieved:
        example = retrieved[0]
        steps_text = example["output"].split("Step ")[1:]
        steps = []
        for s in steps_text:
            try:
                num, rest = s.split(":", 1)
                steps.append({"step": int(num.strip()), "action": rest.strip(), "description": ""})
            except ValueError:
                steps.append({"step": 0, "action": s.strip(), "description": ""})
        return steps

    else:
        return [{"step": 1, "action": f"Do task: {instruction}", "description": "Fallback step"}]

# ----------------------------
# 6️⃣ Send steps to JS
# ----------------------------
def send_to_js(instruction, steps):
    js_data = {
        "instruction": instruction,
        "steps": steps,
        "total_steps": len(steps),
        "status": "ready_for_execution"
    }
    print("📡 Sending JS steps...")
    print(f"📦 Data sent: {json.dumps(js_data, indent=2)}")
    return js_data

# ----------------------------
# 7️⃣ Main loop
# ----------------------------
def main():
    print("🚀 GENERIC JS INSTRUCTION GENERATOR (RAG + Fine-tuned CPU, no torch)")
    print("==============================================================")
    
    while True:
        instruction = input("\n💡 Enter any instruction (or 'quit' to exit): ").strip()
        if instruction.lower() in ['quit', 'exit', 'q']:
            break
        if not instruction:
            continue
        steps = generate_js_steps(instruction, top_k=1)
        print(f"\n✅ STEPS FOR: '{instruction}'")
        for step in steps:
            print(f"Step {step['step']}: {step['action']}")
        js_data = send_to_js(instruction, steps)
        if input("\n🔄 Another instruction? (y/n): ").lower() != 'y':
            break

if __name__ == "__main__":
    main()




# # demo.py - 1
# import json

# def generate_generic_steps(instruction):
#     """Generate completely generic steps for any instruction"""
#     steps = [
#         {
#             "step": 1,
#             "action": f"Start the process for: {instruction}",
#             "description": "Initial setup and navigation"
#         },
#         {
#             "step": 2,
#             "action": f"Execute the main task: {instruction}", 
#             "description": "Perform the core action"
#         },
#         {
#             "step": 3,
#             "action": f"Complete and verify: {instruction}",
#             "description": "Finalize and confirm completion"
#         }
#     ]
#     return steps

# def send_to_esp32(instruction, steps):
#     """Send steps to ESP32"""
#     esp32_data = {
#         "instruction": instruction,
#         "steps": steps,
#         "total_steps": len(steps),
#         "status": "ready_for_execution"
#     }
    
#     # In real implementation, this would send via Serial/USB/WiFi
#     print("📡 SENDING TO ESP32...")
    
#     # Simulate sending data to ESP32
#     print(f"✅ Successfully sent to ESP32!")
#     print(f"📦 Data sent: {json.dumps(esp32_data, indent=2)}")
    
#     return esp32_data

# def main():
#     print("🚀 GENERIC INSTRUCTION TO ESP32")
#     print("================================")
    
#     while True:
#         # Get any instruction from user
#         instruction = input("\n💡 Enter any instruction: ").strip()
        
#         if instruction.lower() in ['quit', 'exit', 'q']:
#             print("👋 Goodbye!")
#             break
            
#         if not instruction:
#             print("❌ Please enter an instruction!")
#             continue
        
#         # Generate generic steps for ANY instruction
#         steps = generate_generic_steps(instruction)
        
#         # Display the steps
#         print(f"\n✅ STEPS FOR: '{instruction}'")
#         print("=" * 40)
        
#         for step in steps:
#             print(f"\nStep {step['step']}: {step['action']}")
#             print(f"   Description: {step['description']}")
        
#         # Send steps to ESP32
#         print(f"\n📤 PASSING TO ESP32...")
#         esp32_data = send_to_esp32(instruction, steps)
        
#         # Show confirmation
#         print(f"\n🎯 ESP32 RECEIVED:")
#         print(f"   Instruction: {esp32_data['instruction']}")
#         print(f"   Steps: {esp32_data['total_steps']}")
#         print(f"   Status: {esp32_data['status']}")
        
#         # Continue?
#         if input("\n🔄 Process another instruction? (y/n): ").lower() != 'y':
#             print("👋 Thank you!")
#             break

# if __name__ == "__main__":
#     main()