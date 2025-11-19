# demo.py - fine-tuned model usage for general software and RAG usage for 2048 game
import json
import os
import sys
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline

# Fix encoding for Windows terminal
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

print("🚀 LLM RAG ASSISTANT - Final Version")
print("====================================")

# ----------------------------
# 1️⃣ Simple Dataset Manager (for 2048 RAG)
# ----------------------------
class SimpleRAGSystem:
    def __init__(self, dataset_path=None):
        if dataset_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            dataset_path = os.path.join(current_dir, "llm_dataset.jsonl")
        self.dataset_path = dataset_path
        self.dataset = self.load_dataset()
        self.setup_retrieval()
        
    def load_dataset(self):
        dataset = []
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            if "instruction" in entry and "output" in entry:
                                dataset.append(entry)
                        except json.JSONDecodeError:
                            continue
            print(f"✅ Loaded {len(dataset)} examples")
        except FileNotFoundError:
            print(f"❌ Dataset file not found: {self.dataset_path}")
        return dataset
    
    def setup_retrieval(self):
        if self.dataset:
            self.instructions = [item["instruction"] for item in self.dataset]
            self.vectorizer = TfidfVectorizer()
            self.embeddings = self.vectorizer.fit_transform(self.instructions)
            print("✅ RAG system ready")
        else:
            self.instructions = []
            self.vectorizer = None
            self.embeddings = None
    
    def retrieve_best_match(self, query):
        if not self.dataset:
            return None
        try:
            query_vec = self.vectorizer.transform([query])
            sims = cosine_similarity(query_vec, self.embeddings)[0]
            best_idx = np.argmax(sims)
            if sims[best_idx] > 0.1:
                return self.dataset[best_idx]
            else:
                return None
        except:
            return None

# ----------------------------
# 2️⃣ Step Extractor
# ----------------------------
class StepExtractor:
    @staticmethod
    def extract_steps_from_output(output_text):
        steps = []
        text = output_text.strip()
        step_matches = re.findall(r'Step\s*(\d+)\s*:\s*([^\.]+\.?)', text, re.IGNORECASE)
        for step_num, action in step_matches:
            try:
                step_num = int(step_num)
                action = action.strip()
                if action:
                    steps.append({"step": step_num, "action": action, "description": f"Step {step_num}: {action}"})
            except ValueError:
                continue

        if not steps:
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            for i, sentence in enumerate(sentences[:6], 1):
                sentence = re.sub(r'^Step\s*\d+\s*[:\.]?\s*', '', sentence, flags=re.IGNORECASE)
                if sentence and len(sentence) > 5:
                    steps.append({"step": i, "action": sentence, "description": f"Step {i}: {sentence}"})

        unique_steps = {}
        for step in steps:
            unique_steps[step["step"]] = step

        sorted_steps = sorted(unique_steps.values(), key=lambda x: x["step"])
        if len(sorted_steps) > 0:
            renumbered_steps = []
            for i, step in enumerate(sorted_steps, 1):
                renumbered_steps.append({"step": i, "action": step["action"], "description": f"Step {i}: {step['action']}"})
            return renumbered_steps
        return sorted_steps

    @staticmethod
    def adapt_steps_for_instruction(retrieved_steps, new_instruction):
        if not retrieved_steps:
            return []
        steps_text = retrieved_steps["output"]
        if "add" in new_instruction.lower():
            steps_text = steps_text.replace("subtract", "add").replace("Subtract", "Add").replace("difference", "sum")
        elif "subtract" in new_instruction.lower():
            steps_text = steps_text.replace("add", "subtract").replace("Add", "Subtract").replace("sum", "difference")
        elif "multiply" in new_instruction.lower():
            steps_text = steps_text.replace("add", "multiply").replace("Add", "Multiply").replace("sum", "product")
        elif "divide" in new_instruction.lower():
            steps_text = steps_text.replace("add", "divide").replace("Add", "Divide").replace("sum", "quotient")
        return StepExtractor.extract_steps_from_output(steps_text)

# ----------------------------
# 3️⃣ Main Assistant
# ----------------------------
class SimpleAssistant:
    def __init__(self):
        print("🔄 Initializing Simple RAG Assistant...")
        # Load RAG dataset (2048 game only)
        self.rag_system = SimpleRAGSystem()
        self.step_extractor = StepExtractor()
        # Load fine-tuned model for general software
        self.load_finetuned_model()
        print("✅ Assistant Ready!")

    def load_finetuned_model(self):
        try:
            # Build path to the latest checkpoint
            base_path = os.path.join(os.path.dirname(__file__), "fine_tuned_js_model")
            checkpoint_dirs = sorted([d for d in os.listdir(base_path) if d.startswith("checkpoint")])
            
            if not checkpoint_dirs:
                print("⚠️ No checkpoints found in fine_tuned_js_model directory")
                self.generator = None
                return
            
            # Use the latest checkpoint
            latest_checkpoint = checkpoint_dirs[-1]
            model_path = os.path.join(base_path, latest_checkpoint)
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True)
            self.generator = pipeline("text2text-generation", model=self.model, tokenizer=self.tokenizer)
            print(f"✅ Fine-tuned model loaded from: {latest_checkpoint}")
        except Exception as e:
            print(f"❌ Failed to load fine-tuned model: {e}")
            self.generator = None

    def get_category(self, query):
        query_lower = query.lower()
        if any(word in query_lower for word in ["2048", "swipe", "game", "play"]):
            return "game_2048"
        elif any(word in query_lower for word in ["add", "subtract", "multiply", "divide", "sum", "product"]):
            return "arithmetic_operations"
        else:
            return "general_software"

    def process_instruction(self, instruction):
        print(f"\n🎯 Processing: '{instruction}'")
        category = self.get_category(instruction)
        print(f"📂 Category: {category}")

        if category == "game_2048":
            print("🔹 Using RAG retrieval for 2048 game")
            best_match = self.rag_system.retrieve_best_match(instruction)
            if best_match:
                steps = self.step_extractor.adapt_steps_for_instruction(best_match, instruction)
                print("✅ RAG steps retrieved")
            else:
                print("⚠️ No match found, using fallback for 2048")
                steps = self.get_fallback_steps(instruction, category)
        elif category == "arithmetic_operations":
            print("🔹Using fine-tuned model for general software")
            best_match = self.rag_system.retrieve_best_match(instruction)
            if best_match:
                steps = self.step_extractor.adapt_steps_for_instruction(best_match, instruction)
                print("✅ Steps retrieved and adapted")
            else:
                print("⚠️ No match found, using fallback for arithmetic")
                steps = self.get_fallback_steps(instruction, category)
        else:
            print("🔹 Using fine-tuned model for general software")
            if self.generator:
                try:
                    # Adjust prompt if your fine-tuned model expects "instruction:" prefix
                    prompt = instruction  # or f"instruction: {instruction}"
                    output = self.generator(prompt, max_length=512)[0]["generated_text"]
                    if output.strip():
                        # Debug: print the raw output
                        print(f"🔍 Model output: {output[:100]}...")
                        steps = StepExtractor.extract_steps_from_output(output)
                        # If extraction failed or returned empty, use fallback with instruction-based steps
                        if not steps or len(steps) == 1:
                            print("⚠️ Model output doesn't contain detailed steps, using enhanced fallback")
                            steps = self.get_fallback_steps(instruction, category)
                        else:
                            print("✅ Steps generated by fine-tuned model")
                    else:
                        print("⚠️ Fine-tuned model output empty, using fallback")
                        steps = self.get_fallback_steps(instruction, category)
                except Exception as e:
                    print(f"❌ Fine-tuned model failed: {e}")
                    steps = self.get_fallback_steps(instruction, category)
            else:
                print("⚠️ Fine-tuned generator not loaded, using fallback")
                steps = self.get_fallback_steps(instruction, category)

        result = {
            "instruction": instruction,
            "category": category,
            "steps": steps,
            "total_steps": len(steps),
            "status": "ready_for_execution"
        }
        return result

    def get_fallback_steps(self, instruction, category):
        if category == "game_2048":
            return [
                {"step": 1, "action": "Focus on the 2048 game window", "description": "Step 1: Focus on the 2048 game window"},
                {"step": 2, "action": "Analyze current tile positions", "description": "Step 2: Analyze current tile positions"},
                {"step": 3, "action": "Execute swipe left action", "description": "Step 3: Execute swipe left action"},
                {"step": 4, "action": "Wait for tiles to merge", "description": "Step 4: Wait for tiles to merge"},
                {"step": 5, "action": "Check for new tile appearance", "description": "Step 5: Check for new tile appearance"}
            ]
        else:
            return [
                {"step": 1, "action": f"Plan implementation for: {instruction}", "description": f"Step 1: Plan implementation for: {instruction}"},
                {"step": 2, "action": "Set up basic structure", "description": "Step 2: Set up basic structure"},
                {"step": 3, "action": "Implement core features", "description": "Step 3: Implement core features"},
                {"step": 4, "action": "Test functionality", "description": "Step 4: Test functionality"},
                {"step": 5, "action": "Debug and refine", "description": "Step 5: Debug and refine"}
            ]

    def interactive_mode(self):
        print("\n" + "="*50)
        print("🤖 SIMPLE RAG ASSISTANT - Ready!")
        print("="*50)
        while True:
            user_input = input("💡 Enter instruction (or 'quit'): ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye!")
                break
            if not user_input:
                continue
            try:
                result = self.process_instruction(user_input)
                print(f"\n✅ STEPS ({result['category']}):")
                for step in result['steps']:
                    print(f"   {step['step']}. {step['action']}")
                print(f"\n📡 JSON ready for JavaScript:")
                print(json.dumps(result, indent=2))
            except Exception as e:
                print(f"❌ Error: {e}")

# ----------------------------
# 4️⃣ Quick Test
# ----------------------------
def test_system():
    print("🧪 Testing system...")
    assistant = SimpleAssistant()
    test_cases = [
        "Create a JS app to add two numbers",
        "Play 2048 game: swipe left",
        "Make a calculator to multiply numbers",
        "Swipe right in 2048 game",
        "Create a JS app to divide numbers"
    ]
    for instruction in test_cases:
        print(f"\n{'='*50}")
        result = assistant.process_instruction(instruction)
        print(f"📝 {instruction}")
        print(f"🏷️  {result['category']} - {len(result['steps'])} steps")
        for step in result['steps'][:3]:
            print(f"   {step['step']}. {step['action'][:50]}...")

# ----------------------------
# 5️⃣ Main Execution
# ----------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_system()
    else:
        assistant = SimpleAssistant()
        assistant.interactive_mode()




# # demo.py - specify ex 1
# import json
# import os
# import numpy as np
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity
# import re

# print("🚀 LLM RAG ASSISTANT - Simple & Effective Version")
# print("================================================")

# # ----------------------------
# # 1️⃣ Simple Dataset Manager
# # ----------------------------
# class SimpleRAGSystem:
#     def __init__(self, dataset_path=None):
#         if dataset_path is None:
#             # Use absolute path relative to this file's directory
#             import os
#             current_dir = os.path.dirname(os.path.abspath(__file__))
#             dataset_path = os.path.join(current_dir, "llm_dataset.jsonl")
#         self.dataset_path = dataset_path
#         self.dataset = self.load_dataset()
#         self.setup_retrieval()
        
#     def load_dataset(self):
#         """Load dataset with error handling"""
#         dataset = []
#         try:
#             with open(self.dataset_path, "r", encoding="utf-8") as f:
#                 for line in f:
#                     line = line.strip()
#                     if line:
#                         try:
#                             entry = json.loads(line)
#                             if "instruction" in entry and "output" in entry:
#                                 dataset.append(entry)
#                         except json.JSONDecodeError:
#                             continue
#             print(f"✅ Loaded {len(dataset)} examples")
#         except FileNotFoundError:
#             print(f"❌ Dataset file not found: {self.dataset_path}")
#         return dataset
    
#     def setup_retrieval(self):
#         """Setup TF-IDF retrieval"""
#         if self.dataset:
#             self.instructions = [item["instruction"] for item in self.dataset]
#             self.vectorizer = TfidfVectorizer()
#             self.embeddings = self.vectorizer.fit_transform(self.instructions)
#             print("✅ RAG system ready")
#         else:
#             self.instructions = []
#             self.vectorizer = None
#             self.embeddings = None
    
#     def get_category(self, query):
#         """Simple category detection"""
#         query_lower = query.lower()
#         if any(word in query_lower for word in ["2048", "swipe", "game", "play"]):
#             return "game_2048"
#         elif any(word in query_lower for word in ["add", "subtract", "multiply", "divide", "sum", "product"]):
#             return "arithmetic_operations"
#         else:
#             return "general_software"
    
#     def retrieve_best_match(self, query):
#         """Retrieve the single best matching example"""
#         if not self.dataset:
#             return None
            
#         try:
#             query_vec = self.vectorizer.transform([query])
#             sims = cosine_similarity(query_vec, self.embeddings)[0]
#             best_idx = np.argmax(sims)
            
#             if sims[best_idx] > 0.1:  # Similarity threshold
#                 return self.dataset[best_idx]
#             else:
#                 return None
#         except:
#             return None

# # ----------------------------
# # 2️⃣ Smart Step Extractor
# # ----------------------------
# class StepExtractor:
#     @staticmethod
#     def extract_steps_from_output(output_text):
#         """Clean and simple step extraction"""
#         steps = []
        
#         # Clean the text
#         text = output_text.strip()
        
#         # Method 1: Look for "Step X: action" pattern
#         step_matches = re.findall(r'Step\s*(\d+)\s*:\s*([^\.]+\.?)', text, re.IGNORECASE)
#         for step_num, action in step_matches:
#             try:
#                 step_num = int(step_num)
#                 action = action.strip()
#                 if action:
#                     steps.append({
#                         "step": step_num,
#                         "action": action,
#                         "description": f"Step {step_num}: {action}"
#                     })
#             except ValueError:
#                 continue
        
#         # Method 2: If no steps found, split by periods and create steps
#         if not steps:
#             sentences = [s.strip() for s in text.split('.') if s.strip()]
#             for i, sentence in enumerate(sentences[:6], 1):
#                 # Clean up the sentence
#                 sentence = re.sub(r'^Step\s*\d+\s*[:\.]?\s*', '', sentence, flags=re.IGNORECASE)
#                 if sentence and len(sentence) > 5:
#                     steps.append({
#                         "step": i,
#                         "action": sentence,
#                         "description": f"Step {i}: {sentence}"
#                     })
        
#         # Remove duplicates and sort by step number
#         unique_steps = {}
#         for step in steps:
#             unique_steps[step["step"]] = step
        
#         sorted_steps = sorted(unique_steps.values(), key=lambda x: x["step"])
        
#         # Renumber if there are gaps or duplicates in step numbers
#         if len(sorted_steps) > 0:
#             renumbered_steps = []
#             for i, step in enumerate(sorted_steps, 1):
#                 renumbered_steps.append({
#                     "step": i,
#                     "action": step["action"],
#                     "description": f"Step {i}: {step['action']}"
#                 })
#             return renumbered_steps
        
#         return sorted_steps
    
#     @staticmethod
#     def adapt_steps_for_instruction(retrieved_steps, new_instruction):
#         """Adapt retrieved steps for the new instruction"""
#         if not retrieved_steps:
#             return []
            
#         steps_text = retrieved_steps["output"]
#         category = "general"
        
#         # Simple adaptations based on instruction content
#         if "add" in new_instruction.lower():
#             steps_text = steps_text.replace("subtract", "add").replace("Subtract", "Add")
#             steps_text = steps_text.replace("difference", "sum")
#         elif "subtract" in new_instruction.lower():
#             steps_text = steps_text.replace("add", "subtract").replace("Add", "Subtract")
#             steps_text = steps_text.replace("sum", "difference")
#         elif "multiply" in new_instruction.lower():
#             steps_text = steps_text.replace("add", "multiply").replace("Add", "Multiply")
#             steps_text = steps_text.replace("sum", "product")
#         elif "divide" in new_instruction.lower():
#             steps_text = steps_text.replace("add", "divide").replace("Add", "Divide")
#             steps_text = steps_text.replace("sum", "quotient")
        
#         return StepExtractor.extract_steps_from_output(steps_text)

# # ----------------------------
# # 3️⃣ Main Assistant
# # ----------------------------
# class SimpleAssistant:
#     def __init__(self):
#         print("🔄 Initializing Simple RAG Assistant...")
#         self.rag_system = SimpleRAGSystem()
#         self.step_extractor = StepExtractor()
#         print("✅ Assistant Ready!")
    
#     def process_instruction(self, instruction):
#         """Process instruction using simple RAG"""
#         print(f"\n🎯 Processing: '{instruction}'")
        
#         # Get category
#         category = self.rag_system.get_category(instruction)
#         print(f"📂 Category: {category}")
        
#         # Retrieve best match
#         best_match = self.rag_system.retrieve_best_match(instruction)
        
#         if best_match:
#             print(f"🔍 Best match: '{best_match['instruction']}'")
            
#             # Extract and adapt steps
#             steps = self.step_extractor.adapt_steps_for_instruction(best_match, instruction)
            
#             if steps:
#                 print("✅ Using adapted RAG steps")
#             else:
#                 print("⚠️ Step extraction failed, using fallback")
#                 steps = self.get_fallback_steps(instruction, category)
#         else:
#             print("⚠️ No good match found, using fallback")
#             steps = self.get_fallback_steps(instruction, category)
        
#         # Prepare result
#         result = {
#             "instruction": instruction,
#             "category": category,
#             "steps": steps,
#             "total_steps": len(steps),
#             "status": "ready_for_execution"
#         }
        
#         return result
    
#     def get_fallback_steps(self, instruction, category):
#         """Get fallback steps based on category"""
#         if category == "game_2048":
#             return [
#                 {"step": 1, "action": "Focus on the 2048 game window", "description": "Step 1: Focus on the 2048 game window"},
#                 {"step": 2, "action": "Analyze current tile positions", "description": "Step 2: Analyze current tile positions"},
#                 {"step": 3, "action": "Execute swipe left action", "description": "Step 3: Execute swipe left action"},
#                 {"step": 4, "action": "Wait for tiles to merge", "description": "Step 4: Wait for tiles to merge"},
#                 {"step": 5, "action": "Check for new tile appearance", "description": "Step 5: Check for new tile appearance"}
#             ]
#         elif category == "arithmetic_operations":
#             return [
#                 {"step": 1, "action": "Create input fields for numbers", "description": "Step 1: Create input fields for numbers"},
#                 {"step": 2, "action": "Create display area for results", "description": "Step 2: Create display area for results"},
#                 {"step": 3, "action": "Add calculate button", "description": "Step 3: Add calculate button"},
#                 {"step": 4, "action": "Implement calculation logic", "description": "Step 4: Implement calculation logic"},
#                 {"step": 5, "action": "Add clear/reset functionality", "description": "Step 5: Add clear/reset functionality"}
#             ]
#         else:
#             return [
#                 {"step": 1, "action": f"Plan implementation for: {instruction}", "description": f"Step 1: Plan implementation for: {instruction}"},
#                 {"step": 2, "action": "Set up basic structure", "description": "Step 2: Set up basic structure"},
#                 {"step": 3, "action": "Implement core features", "description": "Step 3: Implement core features"},
#                 {"step": 4, "action": "Test functionality", "description": "Step 4: Test functionality"},
#                 {"step": 5, "action": "Debug and refine", "description": "Step 5: Debug and refine"}
#             ]
    
#     def interactive_mode(self):
#         """Run interactive mode"""
#         print("\n" + "="*50)
#         print("🤖 SIMPLE RAG ASSISTANT - Ready!")
#         print("="*50)
        
#         while True:
#             print("\n" + "-"*40)
#             user_input = input("💡 Enter instruction (or 'quit'): ").strip()
            
#             if user_input.lower() in ['quit', 'exit', 'q']:
#                 print("👋 Goodbye!")
#                 break
            
#             if not user_input:
#                 continue
            
#             try:
#                 result = self.process_instruction(user_input)
                
#                 print(f"\n✅ STEPS ({result['category']}):")
#                 for step in result['steps']:
#                     print(f"   {step['step']}. {step['action']}")
                
#                 print(f"\n📡 JSON ready for JavaScript:")
#                 print(json.dumps(result, indent=2))
                
#             except Exception as e:
#                 print(f"❌ Error: {e}")

# # ----------------------------
# # 4️⃣ Quick Test
# # ----------------------------
# def test_system():
#     """Test the system with common instructions"""
#     print("🧪 Testing system...")
    
#     assistant = SimpleAssistant()
    
#     test_cases = [
#         "Create a JS app to add two numbers",
#         "Play 2048 game: swipe left",
#         "Make a calculator to multiply numbers",
#         "Swipe right in 2048 game",
#         "Create a JS app to divide numbers"
#     ]
    
#     for instruction in test_cases:
#         print(f"\n{'='*50}")
#         result = assistant.process_instruction(instruction)
#         print(f"📝 {instruction}")
#         print(f"🏷️  {result['category']} - {len(result['steps'])} steps")
#         for step in result['steps'][:3]:
#             print(f"   {step['step']}. {step['action'][:50]}...")

# # ----------------------------
# # 5️⃣ Main Execution
# # ----------------------------
# if __name__ == "__main__":
#     import sys
    
#     if len(sys.argv) > 1 and sys.argv[1] == "--test":
#         test_system()
#     else:
#         assistant = SimpleAssistant()
#         assistant.interactive_mode()



# # demo.py - fine-tune + RAG for all
# import json
# import os
# import numpy as np
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity
# from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
# import torch

# # ----------------------------
# # 1️⃣ Load dataset
# # ----------------------------
# def load_dataset(file_path="llm_dataset.jsonl"):
#     dataset = []
#     try:
#         with open(file_path, "r") as f:
#             for line in f:
#                 dataset.append(json.loads(line))
#     except FileNotFoundError:
#         print(f"❌ Dataset file not found: {file_path}")
#     return dataset

# dataset = load_dataset()
# instructions = [entry["instruction"] for entry in dataset]

# # ----------------------------
# # 2️⃣ Build simple TF-IDF embeddings for retrieval
# # ----------------------------
# vectorizer = TfidfVectorizer()
# dataset_embeddings = vectorizer.fit_transform(instructions)
# print(f"✅ Dataset embeddings ready ({len(instructions)} instructions)")

# # ----------------------------
# # 3️⃣ Load fine-tuned LLM (auto-detect local checkpoint)
# # ----------------------------
# def find_local_checkpoint(base_dir="fine_tuned_js_model"):
#     base_path = os.path.join(os.path.dirname(__file__), base_dir) if '__file__' in globals() else base_dir
#     if os.path.isdir(base_path):
#         root_files = os.listdir(base_path)
#         if any(f in root_files for f in ("config.json", "pytorch_model.bin", "model.safetensors")):
#             return base_path
#         subdirs = [d for d in root_files if os.path.isdir(os.path.join(base_path, d))]
#         checkpoint_dirs = [d for d in subdirs if d.startswith("checkpoint")]
#         if checkpoint_dirs:
#             def ckpt_key(name):
#                 nums = ''.join(ch for ch in name if ch.isdigit())
#                 return int(nums) if nums else 0
#             checkpoint_dirs.sort(key=ckpt_key, reverse=True)
#             for d in checkpoint_dirs:
#                 candidate = os.path.join(base_path, d)
#                 files = os.listdir(candidate)
#                 if any(f in files for f in ("config.json", "pytorch_model.bin", "model.safetensors")):
#                     return candidate
#     return None

# try:
#     model_candidate = find_local_checkpoint("fine_tuned_js_model")
#     if model_candidate is None:
#         raise FileNotFoundError("No local checkpoint found under 'fine_tuned_js_model'")

#     model_name = model_candidate
#     try:
#         tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
#     except Exception:
#         cfg_path = os.path.join(model_name, "config.json")
#         fallback_tokenizer = "t5-small"
#         try:
#             if os.path.exists(cfg_path):
#                 with open(cfg_path, "r", encoding="utf-8") as fh:
#                     cfg = json.load(fh)
#                     if cfg.get("model_type") == "t5":
#                         fallback_tokenizer = "t5-small"
#         except Exception:
#             pass
#         print(f"ℹ️ Tokenizer not found in checkpoint, falling back to '{fallback_tokenizer}' tokenizer")
#         tokenizer = AutoTokenizer.from_pretrained(fallback_tokenizer)
#         try:
#             tokenizer.save_pretrained(model_name)
#             print(f"✅ Saved fallback tokenizer files to: {model_name}")
#         except Exception as _e:
#             print(f"⚠️ Could not save tokenizer to checkpoint: {_e}")

#     model = AutoModelForSeq2SeqLM.from_pretrained(model_name, local_files_only=True)
#     device = torch.device("cpu")
#     model.to(device)
#     fine_tuned_available = True
#     print(f"✅ Fine-tuned model loaded from: {model_name}")
# except Exception as e:
#     print(f"⚠️ Fine-tuned model not found or failed: {e}")
#     print("ℹ️ Tip: set `model_name` manually or install 'safetensors'.")
#     fine_tuned_available = False

# # ----------------------------
# # 4️⃣ RAG retrieval using cosine similarity
# # ----------------------------
# def retrieve_similar_instruction(query, top_k=1):
#     query_vec = vectorizer.transform([query])
#     sims = cosine_similarity(query_vec, dataset_embeddings)[0]
#     top_indices = np.argsort(sims)[::-1][:top_k]
#     return [dataset[i] for i in top_indices]

# # ----------------------------
# # 5️⃣ Generate JS steps using RAG + fine-tuned model
# # ----------------------------
# def generate_js_steps(instruction, top_k=1):
#     retrieved = retrieve_similar_instruction(instruction, top_k=top_k)

#     # 🔍 DEBUG: SHOW RAG RETRIEVAL
#     print("\n🔍 RAG Retrieved Example:")
#     if not retrieved:
#         print("⚠️ No similar instruction found")
#     else:
#         for r in retrieved:
#             print(json.dumps(r, indent=2))

#     if fine_tuned_available and retrieved:
#         context = "\n".join([r["output"] for r in retrieved])
#         prompt = f"Instruction: {instruction}\nUse the following examples as reference:\n{context}\nGenerate steps:"
#         inputs = tokenizer(prompt, return_tensors="pt")
#         for k, v in inputs.items():
#             inputs[k] = v.to(device)
#         with torch.no_grad():
#             gen = model.generate(**inputs, max_new_tokens=256, do_sample=False)
#         steps_text = tokenizer.decode(gen[0], skip_special_tokens=True)
#         steps = []
#         for s in steps_text.split("Step ")[1:]:
#             try:
#                 num, rest = s.split(":", 1)
#                 steps.append({"step": int(num.strip()), "action": rest.strip(), "description": ""})
#             except ValueError:
#                 steps.append({"step": 0, "action": s.strip(), "description": ""})
#         return steps

#     elif retrieved:
#         example = retrieved[0]
#         steps_text = example["output"].split("Step ")[1:]
#         steps = []
#         for s in steps_text:
#             try:
#                 num, rest = s.split(":", 1)
#                 steps.append({"step": int(num.strip()), "action": rest.strip(), "description": ""})
#             except ValueError:
#                 steps.append({"step": 0, "action": s.strip(), "description": ""})
#         return steps

#     else:
#         return [{"step": 1, "action": f"Do task: {instruction}", "description": "Fallback step"}]

# # ----------------------------
# # 6️⃣ Send steps to JS
# # ----------------------------
# def send_to_js(instruction, steps):
#     js_data = {
#         "instruction": instruction,
#         "steps": steps,
#         "total_steps": len(steps),
#         "status": "ready_for_execution"
#     }
#     print("📡 Sending JS steps...")
#     print(f"📦 Data sent: {json.dumps(js_data, indent=2)}")
#     return js_data

# # ----------------------------
# # 7️⃣ Main loop
# # ----------------------------
# def main():
#     print("🚀 GENERIC JS INSTRUCTION GENERATOR (RAG + Fine-tuned CPU, no torch)")
#     print("==============================================================")
    
#     while True:
#         instruction = input("\n💡 Enter any instruction (or 'quit' to exit): ").strip()
#         if instruction.lower() in ['quit', 'exit', 'q']:
#             break
#         if not instruction:
#             continue
#         steps = generate_js_steps(instruction, top_k=1)
#         print(f"\n✅ STEPS FOR: '{instruction}'")
#         for step in steps:
#             print(f"Step {step['step']}: {step['action']}")
#         js_data = send_to_js(instruction, steps)
#         if input("\n🔄 Another instruction? (y/n): ").lower() != 'y':
#             break

# if __name__ == "__main__":
#     main()




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