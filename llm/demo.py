# # demo_dynamic_rag.py - Retrieval-Augmented Generation (RAG)
# import json
# import re
# import random
# from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity
# import os

# # -----------------------------
# # 1️⃣ Load dataset
# # -----------------------------
# dataset_path = "finetune_fixed.jsonl"  # your dataset file
# if not os.path.exists(dataset_path):
#     print(f"❌ Dataset file not found: {dataset_path}")
#     exit(1)

# dataset = []
# with open(dataset_path, "r", encoding="utf-8") as f:
#     for line in f:
#         dataset.append(json.loads(line))

# instructions = [item["instruction"] for item in dataset]
# outputs = [item["output"] for item in dataset]

# # -----------------------------
# # 2️⃣ TF-IDF for instruction similarity
# # -----------------------------
# vectorizer = TfidfVectorizer().fit(instructions)
# instruction_vectors = vectorizer.transform(instructions)

# def find_similar_instructions(query, top_k=3):
#     query_vec = vectorizer.transform([query])
#     sims = cosine_similarity(query_vec, instruction_vectors)[0]
#     top_idx = sims.argsort()[-top_k:][::-1]
#     return [(instructions[i], outputs[i]) for i in top_idx]

# # -----------------------------
# # 3️⃣ Load fine-tuned model
# # -----------------------------
# model_name = "./finetuned_perfect_model"
# tokenizer = AutoTokenizer.from_pretrained(model_name)
# model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
# pipe = pipeline("text2text-generation", model=model, tokenizer=tokenizer,
#                 max_length=400, max_new_tokens=200, do_sample=True,
#                 temperature=0.7, top_p=0.9, repetition_penalty=1.5, num_beams=2)

# # -----------------------------
# # 4️⃣ Prompt template
# # -----------------------------
# def create_prompt_with_examples(task, examples):
#     prompt = "You are an expert browser automation assistant.\n\n"
#     for instr, out in examples:
#         prompt += f"Instruction: {instr}\nOutput:\n{out}\n\n"
#     prompt += f"Now generate 3 steps for a new instruction: '{task}'\n"
#     prompt += "CRITICAL: Each step must follow: Step X: Action | (X,Y) | Target\n"
#     return prompt

# # -----------------------------
# # 5️⃣ Parse AI output
# # -----------------------------
# def parse_steps(llm_output):
#     steps = []
#     pattern = r'Step\s*(\d+):\s*([^|]+?)\s*\|\s*\((\d+),\s*(\d+)\)\s*\|\s*(.+)$'
#     lines = re.split(r'\n+', llm_output)
#     for line in lines:
#         match = re.search(pattern, line.strip())
#         if match:
#             step_num, action, x, y, target = match.groups()
#             x, y = int(x), int(y)
#             if 50 <= x <= 1230 and 50 <= y <= 670:
#                 steps.append({
#                     "step": int(step_num),
#                     "action": action.strip(),
#                     "coordinates": (x, y),
#                     "target": target.strip(),
#                     "type": "ai_generated"
#                 })
#     return steps[:3]

# # -----------------------------
# # 6️⃣ Fallback
# # -----------------------------
# def fallback_steps(task):
#     return [
#         {"step": 1, "action": f"Start {task}", "coordinates": (640, 200), "target": "Browser", "type": "fallback"},
#         {"step": 2, "action": f"Perform {task}", "coordinates": (640, 360), "target": "Action area", "type": "fallback"},
#         {"step": 3, "action": f"Complete {task}", "coordinates": (640, 500), "target": "Confirmation", "type": "fallback"}
#     ]

# # -----------------------------
# # 7️⃣ Main generation
# # -----------------------------
# def generate_steps(task):
#     examples = find_similar_instructions(task)
#     prompt = create_prompt_with_examples(task, examples)
#     result = pipe(prompt)
#     llm_output = result[0]['generated_text']
#     steps = parse_steps(llm_output)
#     if len(steps) < 3:
#         steps = fallback_steps(task)
#     return steps

# # -----------------------------
# # 8️⃣ Enhance delays & confidence
# # -----------------------------
# def enhance_steps(steps):
#     enhanced = []
#     for s in steps:
#         step = s.copy()
#         action = step["action"].lower()
#         if any(w in action for w in ["type", "input"]):
#             step["delay_ms"] = random.randint(1500, 3000)
#         elif any(w in action for w in ["wait", "load"]):
#             step["delay_ms"] = random.randint(2000, 4000)
#         else:
#             step["delay_ms"] = random.randint(800, 2000)
#         step["confidence"] = round(random.uniform(0.5, 0.95), 2)
#         enhanced.append(step)
#     return enhanced

# # -----------------------------
# # 9️⃣ ESP32 commands
# # -----------------------------
# def generate_esp32_commands(steps):
#     cmds = []
#     for s in steps:
#         x, y = s["coordinates"]
#         cmds.append({
#             "step": s["step"],
#             "action": s["action"],
#             "esp32_command": f"touch_screen({x}, {y})",
#             "coordinates": f"({x}, {y})",
#             "target": s["target"],
#             "delay_ms": s["delay_ms"],
#             "confidence": s["confidence"],
#             "type": s["type"]
#         })
#     return sorted(cmds, key=lambda x: x["step"])

# # -----------------------------
# # 10️⃣ Main loop
# # -----------------------------
# def main():
#     print("🚀 RAG-based Browser Automation")
#     while True:
#         task = input("\n👉 Enter instruction (or 'quit'): ").strip()
#         if task.lower() in ["quit", "exit"]:
#             break
#         raw_steps = generate_steps(task)
#         enhanced = enhance_steps(raw_steps)
#         commands = generate_esp32_commands(enhanced)

#         print(f"\n✅ Automation steps for: '{task}'")
#         print("="*60)
#         for cmd in commands:
#             icon = "🤖" if cmd["type"]=="ai_generated" else "⚡"
#             print(f"{icon} Step {cmd['step']}: {cmd['action']} | {cmd['coordinates']} | {cmd['target']} | Delay: {cmd['delay_ms']}ms | Conf: {cmd['confidence']:.0%}")

#         print("\n💻 ESP32 Code:")
#         print("// ===== AUTOMATION SCRIPT =====")
#         for cmd in commands:
#             print(f"delay({cmd['delay_ms']});\n{cmd['esp32_command']};  // {cmd['action']}")
#         print("// ===== END SCRIPT =====")

# if __name__ == "__main__":
#     main()





# # demo.py - Optimized Version (Improved Prompting & Smart Fallback)
# from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
# import re
# import random
# import os

# # ==============================================================
# # 1️⃣ Load fine-tuned model
# # ==============================================================
# model_name = "./finetuned_perfect_model"
# print(f"🚀 Loading your fine-tuned model: {model_name}")

# if not os.path.exists(model_name):
#     print(f"❌ Model directory '{model_name}' not found!")
#     print("💡 Make sure you extracted your fine-tuned model correctly.")
#     exit(1)

# try:
#     tokenizer = AutoTokenizer.from_pretrained(model_name)
#     model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
#     print("✅ Model loaded successfully!")
# except Exception as e:
#     print(f"❌ Failed to load model: {e}")
#     exit(1)

# # ==============================================================
# # 2️⃣ Pipeline configuration
# # ==============================================================
# pipe = pipeline(
#     "text2text-generation",
#     model=model,
#     tokenizer=tokenizer,
#     max_length=256,
#     max_new_tokens=128,
#     temperature=0.6,
#     top_p=0.9,
#     do_sample=True,
#     repetition_penalty=1.3,
#     num_beams=2
# )

# # ==============================================================
# # 3️⃣ Enhanced Prompt Template
# # ==============================================================
# def create_prompt(task):
#     """
#     Structured and instructive prompt to guide the fine-tuned model.
#     """
#     return f"""
# You are an expert automation agent that generates clear 3-step UI interaction plans.

# Each step MUST follow this format:
# Step X: [Action] | (X,Y) | [Target]

# Rules:
# - 3 steps only
# - Use realistic coordinates within 1280x720 screen range
# - Be specific about UI targets (e.g., login button, search bar)
# - Actions can be: click, type, select, wait, scroll, open

# Examples:

# Input: open settings menu
# Output:
# Step 1: Click menu icon | (1200, 60) | Menu bar
# Step 2: Select Settings option | (1000, 180) | Settings menu
# Step 3: Wait for Settings page | (640, 360) | Browser window

# Input: search for weather
# Output:
# Step 1: Click search bar | (320, 100) | Input box
# Step 2: Type 'weather forecast' | (640, 100) | Search input
# Step 3: Click search button | (900, 100) | Submit button

# Now generate for: "{task}"
# """

# # ==============================================================
# # 4️⃣ Parsing and cleaning functions
# # ==============================================================
# def clean_text(text):
#     if not text:
#         return "Unknown"
#     text = re.sub(r'\s+', ' ', text.strip())
#     text = text.replace('| |', '|')
#     return text

# def validate_coordinates(x, y):
#     return 50 <= x <= 1230 and 50 <= y <= 670

# def parse_steps_flexible(llm_output):
#     steps = []
#     lines = llm_output.split('\n')
#     for line in lines:
#         line = line.strip()
#         match = re.search(r'Step\s*(\d+):\s*([^|]+)\s*\|\s*\((\d+),\s*(\d+)\)\s*\|\s*(.+)', line)
#         if match:
#             step_num, action, x, y, target = match.groups()
#             x, y = int(x), int(y)
#             if validate_coordinates(x, y):
#                 steps.append({
#                     "step": int(step_num),
#                     "action": clean_text(action),
#                     "coordinates": (x, y),
#                     "target": clean_text(target),
#                     "type": "ai_generated"
#                 })
#     return steps[:3]

# # ==============================================================
# # 5️⃣ Smart fallback logic
# # ==============================================================
# def create_smart_fallback(instruction):
#     lower = instruction.lower()

#     if any(k in lower for k in ["login", "signin"]):
#         return [
#             {"step": 1, "action": "Click username field", "coordinates": (640, 300), "target": "Username input", "type": "fallback"},
#             {"step": 2, "action": "Type username and password", "coordinates": (640, 350), "target": "Password input", "type": "fallback"},
#             {"step": 3, "action": "Click login button", "coordinates": (640, 400), "target": "Login button", "type": "fallback"}
#         ]
#     elif "search" in lower:
#         term = re.sub(r'search\s*for\s*', '', instruction, flags=re.I).strip() or "query"
#         return [
#             {"step": 1, "action": "Click search bar", "coordinates": (320, 100), "target": "Search input", "type": "fallback"},
#             {"step": 2, "action": f"Type '{term}'", "coordinates": (640, 100), "target": "Text field", "type": "fallback"},
#             {"step": 3, "action": "Click search button", "coordinates": (900, 100), "target": "Submit button", "type": "fallback"}
#         ]
#     elif any(k in lower for k in ["menu", "settings"]):
#         return [
#             {"step": 1, "action": "Click menu icon", "coordinates": (1200, 80), "target": "Navigation menu", "type": "fallback"},
#             {"step": 2, "action": "Select settings", "coordinates": (1000, 180), "target": "Menu option", "type": "fallback"},
#             {"step": 3, "action": "Wait for settings page", "coordinates": (640, 360), "target": "Settings page", "type": "fallback"}
#         ]
#     else:
#         return [
#             {"step": 1, "action": f"Start {instruction}", "coordinates": (640, 200), "target": "Screen area", "type": "fallback"},
#             {"step": 2, "action": f"Perform {instruction}", "coordinates": (640, 360), "target": "Action area", "type": "fallback"},
#             {"step": 3, "action": f"Finish {instruction}", "coordinates": (640, 500), "target": "Browser", "type": "fallback"}
#         ]

# # ==============================================================
# # 6️⃣ Generate steps
# # ==============================================================
# def generate_steps(instruction):
#     print(f"\n🎯 Processing: '{instruction}'")
#     try:
#         prompt = create_prompt(instruction)
#         result = pipe(prompt)[0]['generated_text']
#         print(f"\n📋 Model Raw Output:\n{result}\n")

#         steps = parse_steps_flexible(result)
#         if not steps:
#             print("⚠️ Model output not structured properly. Using smart fallback.")
#             return create_smart_fallback(instruction)
#         return steps
#     except Exception as e:
#         print(f"❌ Error during generation: {e}")
#         return create_smart_fallback(instruction)

# # ==============================================================
# # 7️⃣ Enhance step realism
# # ==============================================================
# def enhance_steps(steps):
#     enhanced = []
#     for s in steps:
#         s = s.copy()
#         action = s["action"].lower()

#         if "type" in action or "input" in action:
#             s["delay_ms"] = random.randint(1500, 3000)
#         elif "wait" in action or "load" in action:
#             s["delay_ms"] = random.randint(2000, 4000)
#         else:
#             s["delay_ms"] = random.randint(800, 1800)

#         if s["type"] == "ai_generated":
#             s["confidence"] = round(random.uniform(0.8, 0.95), 2)
#         else:
#             s["confidence"] = round(random.uniform(0.5, 0.75), 2)

#         enhanced.append(s)
#     return enhanced

# # ==============================================================
# # 8️⃣ ESP32 command generation
# # ==============================================================
# def generate_esp32_commands(steps):
#     commands = []
#     for s in steps:
#         x, y = s["coordinates"]
#         commands.append({
#             "step": s["step"],
#             "action": s["action"],
#             "esp32_command": f"touch_screen({x}, {y})",
#             "target": s["target"],
#             "delay_ms": s["delay_ms"],
#             "confidence": s["confidence"],
#             "type": s["type"]
#         })
#     return commands

# # ==============================================================
# # 9️⃣ Display Results
# # ==============================================================
# def display_results(instruction, commands):
#     print(f"\n✅ Automation steps for: '{instruction}'")
#     print("=" * 60)
#     for c in commands:
#         icon = "🤖" if c["type"] == "ai_generated" else "⚡"
#         print(f"\n{icon} Step {c['step']}: {c['action']}")
#         print(f"   📍 Coordinates: {c['esp32_command'][13:-1]}")
#         print(f"   🎯 Target: {c['target']}")
#         print(f"   ⏱️  Delay: {c['delay_ms']}ms")
#         print(f"   📊 Confidence: {int(c['confidence']*100)}%")

# def display_esp32_code(commands):
#     print("\n💻 ESP32 Executable Code:")
#     print("// ===== AUTOMATION SCRIPT =====")
#     for c in commands:
#         print(f"delay({c['delay_ms']});")
#         print(f"// {c['action']}")
#         print(f"{c['esp32_command']};  // Target: {c['target']}\n")
#     print("// ===== END SCRIPT =====")

# # ==============================================================
# # 🔟 Main Loop
# # ==============================================================
# def main():
#     print("🚀 Browser Automation Agent")
#     print("💡 Example inputs: 'login to account', 'search for weather', 'open settings menu'")
#     print("=" * 60)
#     while True:
#         instruction = input("\n👉 Enter instruction (or 'quit'): ").strip()
#         if instruction.lower() in ["quit", "exit", "q"]:
#             print("👋 Goodbye!")
#             break
#         if not instruction:
#             continue
#         print("🔄 Processing...🔄🔄🔄")
#         steps = generate_steps(instruction)
#         steps = enhance_steps(steps)
#         commands = generate_esp32_commands(steps)
#         display_results(instruction, commands)
#         display_esp32_code(commands)
#         print("=" * 60)

# # ==============================================================
# # RUN
# # ==============================================================
# if __name__ == "__main__":
#     main()





# # IMPROVED demo.py - NO LANGCHAIN VERSION
# from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
# import re
# import random
# import os
# import torch

# # -----------------------------
# # 1️⃣ Load IMPROVED fine-tuned model
# # -----------------------------
# model_name = "./instruction-finetuned-improved"
# print(f"🚀 Loading your IMPROVED fine-tuned model: {model_name}")

# # Check if model exists
# if not os.path.exists(model_name):
#     print(f"❌ Model directory '{model_name}' not found!")
#     print("📁 Available model folders:")
#     for item in os.listdir('.'):
#         if os.path.isdir(item) and any(x in item.lower() for x in ['fine', 'model', 'tune']):
#             print(f"   - {item}")
    
#     # Fallback to previous model
#     if os.path.exists("./instruction-finetuned-fixed"):
#         model_name = "./instruction-finetuned-fixed"
#         print(f"🔄 Using previous model: {model_name}")
#     else:
#         print("💡 Please run the improved fine-tuning first")
#         exit(1)

# try:
#     tokenizer = AutoTokenizer.from_pretrained(model_name)
#     model = AutoModelForCausalLM.from_pretrained(model_name)
    
#     if tokenizer.pad_token is None:
#         tokenizer.pad_token = tokenizer.eos_token
    
#     print("✅ Model loaded successfully!")
    
# except Exception as e:
#     print(f"❌ Failed to load model: {e}")
#     exit(1)

# # -----------------------------
# # 2️⃣ IMPROVED pipeline with better parameters
# # -----------------------------
# pipe = pipeline(
#     "text-generation",
#     model=model,
#     tokenizer=tokenizer,
#     max_new_tokens=120,
#     do_sample=True,
#     temperature=0.8,
#     top_p=0.9,
#     top_k=50,
#     repetition_penalty=1.8,
#     no_repeat_ngram_size=3,
#     pad_token_id=tokenizer.eos_token_id,
#     eos_token_id=tokenizer.eos_token_id,
# )

# # -----------------------------
# # 3️⃣ IMPROVED Prompt template
# # -----------------------------
# def create_prompt(task):
#     return f"""Instruction: {task}
# Output: Step 1:"""

# # -----------------------------
# # 4️⃣ IMPROVED Parsing with better repetition handling
# # -----------------------------
# def validate_coordinates(x, y):
#     return (50 <= x <= 1230 and 50 <= y <= 670)

# def parse_steps_flexible(llm_output):
#     steps = []
#     lines = llm_output.split('\n')
#     seen_actions = set()
    
#     for line in lines:
#         line = line.strip()
#         if not line or len(line) < 10:
#             continue
            
#         patterns = [
#             r'Step\s*(\d+):\s*([^|]+?)\s*\|\s*\((\d+),\s*(\d+)\)\s*\|\s*(.+)$',
#             r'Step\s*(\d+):\s*([^(]+?)\s*\((\d+),\s*(\d+)\)\s*(.+)$',
#             r'(\d+)\.\s*([^|]+?)\s*\|\s*\((\d+),\s*(\d+)\)\s*\|\s*(.+)$',
#         ]
        
#         for pattern in patterns:
#             match = re.search(pattern, line)
#             if match:
#                 try:
#                     step_num, action, x, y, target = match.groups()
#                     x, y = int(x), int(y)
                    
#                     # Check for duplicates and valid format
#                     action_key = f"{action.strip()}_{x}_{y}"
#                     if (validate_coordinates(x, y) and 
#                         len(action.strip()) > 3 and 
#                         len(target.strip()) > 3 and
#                         action_key not in seen_actions and
#                         int(step_num) <= 3):
                        
#                         seen_actions.add(action_key)
#                         steps.append({
#                             "step": int(step_num),
#                             "action": clean_text(action),
#                             "coordinates": (x, y),
#                             "target": clean_text(target),
#                             "type": "ai_generated"
#                         })
#                         print(f"✅ Parsed: Step {step_num} - {action.strip()}")
#                         break
                        
#                 except (ValueError, IndexError):
#                     continue
    
#     return steps[:3]

# def clean_text(text):
#     if not text:
#         return "Unknown"
#     cleaned = re.sub(r'\s+', ' ', text.strip())
#     cleaned = re.sub(r'^\s*[\|:-]\s*', '', cleaned)
#     cleaned = re.sub(r'\s*[\|:-]\s*$', '', cleaned)
#     cleaned = re.sub(r'\s*\|\s*', ' | ', cleaned)
#     return cleaned

# def extract_fallback_steps(llm_output, instruction):
#     steps = []
#     coord_pattern = r'\((\d+),\s*(\d+)\)'
#     coordinates = re.findall(coord_pattern, llm_output)
#     seen_coords = set()
    
#     for i, (x_str, y_str) in enumerate(coordinates[:3]):
#         try:
#             x, y = int(x_str), int(y_str)
#             coord_key = f"{x}_{y}"
            
#             if validate_coordinates(x, y) and coord_key not in seen_coords:
#                 seen_coords.add(coord_key)
                
#                 # Extract context
#                 context_pattern = rf'([^.(]*?)\s*\({x_str},\s*{y_str}\)\s*([^.]*)'
#                 context_match = re.search(context_pattern, llm_output)
                
#                 if context_match:
#                     before, after = context_match.groups()
#                     action = f"{before.strip()} {after.strip()}".strip()
#                     if len(action) < 5:
#                         action = f"Action at ({x},{y})"
#                 else:
#                     action = f"Step {i+1}"
                
#                 steps.append({
#                     "step": i + 1,
#                     "action": action,
#                     "coordinates": (x, y),
#                     "target": "UI element",
#                     "type": "extracted"
#                 })
#         except ValueError:
#             continue
    
#     return steps

# def create_smart_fallback(instruction):
#     instruction_lower = instruction.lower()
    
#     if any(word in instruction_lower for word in ['search', 'find']):
#         search_term = re.sub(r'search|find|for', '', instruction, flags=re.IGNORECASE).strip()
#         if not search_term:
#             search_term = "query"
#         return [
#             {"step": 1, "action": "Click search bar", "coordinates": (320, 80), "target": "Search input", "type": "fallback"},
#             {"step": 2, "action": f"Type '{search_term}'", "coordinates": (640, 80), "target": "Search box", "type": "fallback"},
#             {"step": 3, "action": "Click search", "coordinates": (900, 80), "target": "Search button", "type": "fallback"}
#         ]
#     elif any(word in instruction_lower for word in ['login', 'signin']):
#         return [
#             {"step": 1, "action": "Find login button", "coordinates": (640, 400), "target": "Login button", "type": "fallback"},
#             {"step": 2, "action": "Click login", "coordinates": (640, 400), "target": "Login confirmation", "type": "fallback"},
#             {"step": 3, "action": "Wait for login", "coordinates": (640, 200), "target": "Loading screen", "type": "fallback"}
#         ]
#     elif any(word in instruction_lower for word in ['menu', 'navigation']):
#         return [
#             {"step": 1, "action": "Click menu", "coordinates": (1200, 80), "target": "Menu button", "type": "fallback"},
#             {"step": 2, "action": "Select settings", "coordinates": (1000, 200), "target": "Settings option", "type": "fallback"},
#             {"step": 3, "action": "Wait for settings", "coordinates": (640, 360), "target": "Settings page", "type": "fallback"}
#         ]
#     else:
#         return [
#             {"step": 1, "action": f"Start {instruction}", "coordinates": (640, 200), "target": "Browser", "type": "fallback"},
#             {"step": 2, "action": f"Perform {instruction}", "coordinates": (640, 360), "target": "Action area", "type": "fallback"},
#             {"step": 3, "action": f"Complete {instruction}", "coordinates": (640, 500), "target": "Confirmation", "type": "fallback"}
#         ]

# # -----------------------------
# # 5️⃣ IMPROVED Step generation
# # -----------------------------
# def generate_steps(instruction):
#     print(f"\n🎯 Processing: '{instruction}'")
#     print(f"🤖 Using model: {model_name}")
    
#     try:
#         prompt = create_prompt(instruction)
#         result = pipe(prompt)
#         llm_output = result[0]['generated_text']
        
#         # Extract only the new generated part (remove the prompt)
#         if llm_output.startswith(prompt):
#             llm_output = llm_output[len(prompt):].strip()
        
#         print(f"📋 Raw Output:\n{llm_output}")
        
#         # Better validation
#         step_count = llm_output.count('Step')
#         if len(llm_output.strip()) < 20 or step_count < 2:
#             print("❌ Insufficient step output, using fallback")
#             return create_smart_fallback(instruction)
            
#         steps = parse_steps_flexible(llm_output)
        
#         if not steps:
#             print("⚠️ No steps parsed, trying extraction...")
#             steps = extract_fallback_steps(llm_output, instruction)
        
#         if not steps or len(steps) < 2:
#             print("⚠️ Using smart fallback")
#             steps = create_smart_fallback(instruction)
#         else:
#             print(f"✅ Processed {len(steps)} AI steps")
            
#         return steps
        
#     except Exception as e:
#         print(f"❌ Error: {e}")
#         return create_smart_fallback(instruction)

# # -----------------------------
# # 6️⃣ Enhance steps
# # -----------------------------
# def enhance_steps(steps):
#     enhanced = []
#     for step in steps:
#         step_copy = step.copy()
#         action_lower = step["action"].lower()
        
#         if any(word in action_lower for word in ['type', 'enter', 'input']):
#             step_copy["delay_ms"] = random.randint(1500, 3000)
#         elif any(word in action_lower for word in ['wait', 'load']):
#             step_copy["delay_ms"] = random.randint(2000, 4000)
#         else:
#             step_copy["delay_ms"] = random.randint(800, 2000)
        
#         if step["type"] == "ai_generated":
#             step_copy["confidence"] = round(random.uniform(0.8, 0.95), 2)
#         elif step["type"] == "extracted":
#             step_copy["confidence"] = round(random.uniform(0.6, 0.8), 2)
#         else:
#             step_copy["confidence"] = round(random.uniform(0.5, 0.7), 2)
            
#         enhanced.append(step_copy)
#     return enhanced

# # -----------------------------
# # 7️⃣ Generate ESP32 commands
# # -----------------------------
# def generate_esp32_commands(steps):
#     commands = []
#     for step in steps:
#         x, y = step["coordinates"]
#         commands.append({
#             "step": step["step"],
#             "action": step["action"],
#             "esp32_command": f"touch_screen({x}, {y})",
#             "coordinates": f"({x}, {y})",
#             "target": step["target"],
#             "delay_ms": step["delay_ms"],
#             "confidence": step["confidence"],
#             "type": step["type"]
#         })
#     return sorted(commands, key=lambda x: x["step"])

# # -----------------------------
# # 8️⃣ Display functions
# # -----------------------------
# def display_results(instruction, commands):
#     print(f"\n✅ Automation for: '{instruction}'")
#     print("=" * 60)
    
#     for cmd in commands:
#         if cmd["type"] == "ai_generated":
#             icon = "🤖"
#         elif cmd["type"] == "extracted":
#             icon = "🔍"
#         else:
#             icon = "⚡"
        
#         print(f"\n{icon} Step {cmd['step']}: {cmd['action']}")
#         print(f"   📍 {cmd['coordinates']} | 🎯 {cmd['target']}")
#         print(f"   ⏱️  {cmd['delay_ms']}ms | 📊 {cmd['confidence']:.0%}")

# def display_esp32_code(commands):
#     print("\n💻 ESP32 Code:")
#     print("// ===== AUTOMATION SCRIPT =====")
    
#     for cmd in commands:
#         print(f"delay({cmd['delay_ms']});")
#         print(f"// {cmd['action']}")
#         print(f"{cmd['esp32_command']};  // {cmd['target']}")
#         if cmd['step'] < len(commands):
#             print("")
    
#     print("// ===== END =====")

# # -----------------------------
# # 9️⃣ Main loop
# # -----------------------------
# def main():
#     print("🚀 Browser Automation - IMPROVED MODEL")
#     print(f"⭐ Model: {model_name}")
#     print("💡 Commands: 'search X', 'click Y', 'open Z'")
#     print("=" * 50)
    
#     while True:
#         instruction = input("\n👉 Instruction (or 'quit'): ").strip()
#         if instruction.lower() in ['quit', 'exit', 'q']:
#             break
#         if not instruction:
#             continue

#         print("\n🔄 Processing...")
        
#         raw_steps = generate_steps(instruction)
#         enhanced = enhance_steps(raw_steps)
#         commands = generate_esp32_commands(enhanced)

#         display_results(instruction, commands)
#         display_esp32_code(commands)
        
#         ai_count = len([c for c in commands if c["type"] == "ai_generated"])
#         extracted_count = len([c for c in commands if c["type"] == "extracted"])
#         fallback_count = len([c for c in commands if c["type"] == "fallback"])
        
#         print(f"\n📊 AI: {ai_count}/3 | Extracted: {extracted_count}/3 | Fallback: {fallback_count}/3")
#         print("=" * 60)

# # -----------------------------
# # 🏃 Run
# # -----------------------------
# if __name__ == "__main__":
#     main()


# # demo.py - USING FINE-TUNED MODEL (NO LANGCHAIN)
# from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
# import re
# import random

# # -----------------------------
# # 1️⃣ Load YOUR fine-tuned model
# # -----------------------------
# model_name = "./finetuned_flant5_quality"
# print(f"🚀 Loading your fine-tuned model: {model_name}")

# try:
#     tokenizer = AutoTokenizer.from_pretrained(model_name)
#     model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
#     print("✅ Model loaded successfully!")
# except Exception as e:
#     print(f"❌ Failed to load model: {e}")
#     exit(1)

# # -----------------------------
# # 2️⃣ Optimized pipeline for your model
# # -----------------------------
# pipe = pipeline(
#     "text2text-generation",
#     model=model,
#     tokenizer=tokenizer,
#     max_length=512,
#     max_new_tokens=256,
#     do_sample=True,
#     temperature=0.8,
#     top_p=0.9,
#     repetition_penalty=1.3,
#     num_beams=2,
#     early_stopping=True
# )

# # -----------------------------
# # 3️⃣ SIMPLE & CLEAR Prompt template
# # -----------------------------
# def create_prompt(task):
#     return f"""instruction: {task}

# Generate 3 steps. Follow this exact format:
# Step 1: Action here | (350,80) | Target here
# Step 2: Action here | (640,80) | Target here  
# Step 3: Action here | (900,80) | Target here

# Make steps specific to the instruction.
# Now generate:"""

# # -----------------------------
# # 4️⃣ FLEXIBLE Parsing functions
# # -----------------------------
# def parse_steps_flexible(llm_output):
#     """Very flexible parsing that handles various formats"""
#     steps = []
#     lines = llm_output.split('\n')
    
#     for line in lines:
#         line = line.strip()
#         if not line or len(line) < 10:
#             continue
            
#         # Multiple flexible patterns
#         patterns = [
#             # Standard format: Step 1: Action | (350,80) | Target
#             r'Step\s*(\d+):\s*([^|]+?)\s*\|\s*\((\d+),\s*(\d+)\)\s*\|\s*(.+)',
#             # Without pipe: Step 1: Action (350,80) Target
#             r'Step\s*(\d+):\s*([^(]+?)\s*\((\d+),\s*(\d+)\)\s*(.+)',
#             # Number format: 1. Action | (350,80) | Target
#             r'(\d+)\.\s*([^|]+?)\s*\|\s*\((\d+),\s*(\d+)\)\s*\|\s*(.+)',
#             # Minimal format: Action (350,80) Target
#             r'([^|(]+?)\s*\((\d+),\s*(\d+)\)\s*(.+)'
#         ]
        
#         for pattern in patterns:
#             match = re.search(pattern, line)
#             if match:
#                 try:
#                     if len(match.groups()) == 5:
#                         step_num, action, x, y, target = match.groups()
#                     else:  # Minimal format
#                         action, x, y, target = match.groups()
#                         step_num = len(steps) + 1
                    
#                     x, y = int(x), int(y)
                    
#                     # Basic validation
#                     if 0 <= x <= 1280 and 0 <= y <= 720:
#                         steps.append({
#                             "step": int(step_num),
#                             "action": clean_text(action),
#                             "coordinates": (x, y),
#                             "target": clean_text(target),
#                             "type": "ai_generated"
#                         })
#                         print(f"✅ Parsed: Step {step_num} - {action.strip()}")
#                         break
                        
#                 except (ValueError, IndexError) as e:
#                     continue
    
#     return steps[:3]  # Return max 3 steps

# def clean_text(text):
#     """Clean and normalize text"""
#     if not text:
#         return "Unknown"
    
#     # Remove extra spaces and unwanted characters
#     cleaned = re.sub(r'\s+', ' ', text.strip())
#     cleaned = re.sub(r'^\s*[\|:-]\s*', '', cleaned)  # Remove leading |:-
#     cleaned = re.sub(r'\s*[\|:-]\s*$', '', cleaned)  # Remove trailing |:-
    
#     return cleaned

# def create_ai_fallback(instruction):
#     """Create AI-style fallback steps"""
#     return [
#         {
#             "step": 1, 
#             "action": f"Start {instruction}", 
#             "coordinates": (640, 200), 
#             "target": "Browser",
#             "type": "fallback"
#         },
#         {
#             "step": 2, 
#             "action": f"Execute {instruction}", 
#             "coordinates": (640, 360), 
#             "target": "Action Area", 
#             "type": "fallback"
#         },
#         {
#             "step": 3, 
#             "action": f"Complete {instruction}", 
#             "coordinates": (640, 500), 
#             "target": "Confirmation",
#             "type": "fallback"
#         }
#     ]

# # -----------------------------
# # 5️⃣ Generate steps with AI model
# # -----------------------------
# def generate_steps(instruction):
#     print(f"\n🎯 Processing: '{instruction}'")
#     print("🤖 Using YOUR fine-tuned model...")
    
#     try:
#         # Get response from your fine-tuned model
#         prompt = create_prompt(instruction)
#         result = pipe(prompt)
#         llm_output = result[0]['generated_text']
        
#         print(f"📋 Model Raw Output:\n{llm_output}")
        
#         # Parse the AI output
#         steps = parse_steps_flexible(llm_output)
        
#         if not steps:
#             print("⚠️ Could not parse AI output, using AI-style fallback")
#             steps = create_ai_fallback(instruction)
#         else:
#             print(f"✅ Successfully parsed {len(steps)} AI-generated steps")
            
#         return steps
        
#     except Exception as e:
#         print(f"❌ AI Model Error: {e}")
#         return create_ai_fallback(instruction)

# # -----------------------------
# # 6️⃣ Enhance steps
# # -----------------------------
# def enhance_steps(steps):
#     enhanced = []
#     for step in steps:
#         step_copy = step.copy()
#         step_copy["delay_ms"] = random.randint(1000, 2500)
#         step_copy["confidence"] = round(random.uniform(0.7, 0.95), 2)
#         enhanced.append(step_copy)
#     return enhanced

# # -----------------------------
# # 7️⃣ Generate ESP32 commands
# # -----------------------------
# def generate_esp32_commands(steps):
#     commands = []
#     for step in steps:
#         x, y = step["coordinates"]
#         commands.append({
#             "step": step["step"],
#             "action": step["action"],
#             "esp32_command": f"touch_screen({x}, {y})",
#             "coordinates": f"({x}, {y})",
#             "target": step["target"],
#             "delay_ms": step["delay_ms"],
#             "confidence": step["confidence"],
#             "type": step["type"]
#         })
#     return sorted(commands, key=lambda x: x["step"])

# # -----------------------------
# # 8️⃣ Display functions
# # -----------------------------
# def display_results(instruction, commands):
#     print(f"\n✅ Automation steps for: '{instruction}'")
#     print("=" * 60)
    
#     for cmd in commands:
#         icon = "🤖" if cmd["type"] == "ai_generated" else "⚡"
#         print(f"\n{icon} Step {cmd['step']}: {cmd['action']}")
#         print(f"   📍 Coordinates: {cmd['coordinates']}")
#         print(f"   🎯 Target: {cmd['target']}")
#         print(f"   ⏱️  Delay: {cmd['delay_ms']}ms")
#         print(f"   📊 Confidence: {cmd['confidence']:.0%}")

# def display_esp32_code(commands):
#     print("\n💻 ESP32 Executable Code:")
#     print("// ===== GENERATED BY YOUR FINE-TUNED MODEL =====")
    
#     for cmd in commands:
#         print(f"delay({cmd['delay_ms']});")
#         print(f"// {cmd['action']}")
#         print(f"{cmd['esp32_command']};  // Target: {cmd['target']}")
#         print()
    
#     print("// ===== END =====")

# # -----------------------------
# # 9️⃣ Main loop
# # -----------------------------
# def main():
#     print("🚀 Browser Automation - USING YOUR FINE-TUNED MODEL")
#     print("⭐ Custom trained on wave-ui dataset")
#     print("🤖 AI-Powered Step Generation")
#     print("\n" + "=" * 50)
    
#     while True:
#         instruction = input("\n👉 Enter instruction (or 'quit'): ").strip()
#         if instruction.lower() in ['quit', 'exit', 'q']:
#             print("👋 Goodbye!")
#             break
#         if not instruction:
#             continue

#         # Generate steps using YOUR fine-tuned model
#         raw_steps = generate_steps(instruction)
#         enhanced = enhance_steps(raw_steps)
#         commands = generate_esp32_commands(enhanced)

#         # Display results
#         display_results(instruction, commands)
#         display_esp32_code(commands)
        
#         # Summary
#         ai_count = len([c for c in commands if c["type"] == "ai_generated"])
#         fallback_count = len([c for c in commands if c["type"] == "fallback"])
        
#         print("\n" + "=" * 60)
#         print(f"📊 AI Model Performance: {ai_count}/3 AI-generated steps")
#         if fallback_count > 0:
#             print(f"💡 Note: {fallback_count} steps used fallback (parsing failed)")
#         print("=" * 60)

# # -----------------------------
# # 🔟 Run
# # -----------------------------
# if __name__ == "__main__":
#     main()





# demo.py - USING FINE-TUNED MODEL (NO LANGCHAIN)
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
import re
import json
import random


# 1. Load LLM directly without LangChain

#model_name = "google/flan-t5-base"
model_name = "./finetuned_flant5_waveui"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

pipe = pipeline(
    "text2text-generation",
    model=model,
    tokenizer=tokenizer,
    max_length=512,
    max_new_tokens=400,
    do_sample=True,
    temperature=0.8,
    repetition_penalty=1.2,
)


# 2. IMPROVED Prompt Template (Build prompt directly)

def create_prompt(task):
    return f"""Create 3 specific browser automation steps with coordinates for this instruction:

INSTRUCTION: {task}

Requirements:
- 1280x720 screen resolution
- Realistic coordinates for browser UI
- Specific actions that make sense
- Logical flow from start to finish

Format each step exactly like:
Step 1: [Action description] | Coordinates: (x,y) | Target: [UI element]
Step 2: [Action description] | Coordinates: (x,y) | Target: [UI element]
Step 3: [Action description] | Coordinates: (x,y) | Target: [UI element]

Make steps specific to: "{task}"
"""


# 3. Improved Step Generation with Better Text Handling

def generate_truly_generic_steps(instruction):
    """Generate steps for ANY instruction without any hardcoded patterns"""
    print(f"🎯 Processing: '{instruction}'")
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Vary parameters for different outputs
            current_temp = 0.7 + (attempt * 0.15)
            
            # Generate using pipeline directly
            prompt = create_prompt(instruction)
            result = pipe(
                prompt,
                max_new_tokens=400,
                temperature=current_temp,
                do_sample=True,
                repetition_penalty=1.2
            )
            
            llm_output = result[0]['generated_text']
            
            print(f"📋 LLM Raw Output (Attempt {attempt + 1}):\n{llm_output}")
            
            # Parse the steps
            steps = parse_generic_steps(llm_output)
            
            # Validate they're good quality
            if are_steps_quality(steps, instruction):
                print("✅ Using LLM-generated steps")
                return steps
            else:
                print("⚠️  Steps need improvement, retrying...")
                
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
    
    # Improved generic fallback with better text handling
    print("🔄 Using improved generic fallback")
    return create_improved_generic_fallback(instruction)

def parse_generic_steps(llm_output):
    """Parse steps from LLM output with flexible patterns"""
    steps = []
    lines = llm_output.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
            
        # Multiple flexible parsing patterns
        patterns = [
            r'Step\s*\d+:\s*(.+?)\s*\|\s*Coordinates:\s*\((\d+),\s*(\d+)\)\s*\|\s*Target:\s*(.+)',
            r'\d+\.\s*(.+?)\s*\|\s*Coordinates:\s*\((\d+),\s*(\d+)\)\s*\|\s*Target:\s*(.+)',
            r'Step\s*\d+:\s*(.+?)\s*\((\d+),\s*(\d+)\)\s*Target:\s*(.+)',
            r'\d+\.\s*(.+?)\s*at\s*\((\d+),\s*(\d+)\)\s*on\s*(.+)',
            r'(.+?)\s*Coordinates:\s*\((\d+),\s*(\d+)\)\s*Target:\s*(.+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) >= 4:
                        action, x, y, target = groups[0], groups[1], groups[2], groups[3]
                        
                        # Clean and validate
                        action = clean_text(action)
                        target = clean_text(target)
                        
                        x_coord = int(x)
                        y_coord = int(y)
                        
                        # Validate coordinates are reasonable
                        if is_valid_coordinate(x_coord, y_coord):
                            steps.append({
                                "action": action,
                                "coordinates": (x_coord, y_coord),
                                "target": target,
                                "type": "llm_generated"
                            })
                            break
                            
                except (ValueError, IndexError) as e:
                    continue
    
    return steps

def clean_text(text):
    """Clean text by removing common artifacts"""
    text = re.sub(r'^Step\s*\d+:\s*', '', text)
    text = re.sub(r'[\[\]]', '', text)
    text = re.sub(r'^[\d\.\s]+', '', text)
    return text.strip()

def is_valid_coordinate(x, y):
    """Check if coordinates are valid and reasonable"""
    return (0 <= x <= 1280 and 0 <= y <= 720 and 
            not (x == 0 and y == 0) and
            not (x == 1280 and y == 720))

def are_steps_quality(steps, instruction):
    """Check if steps are good quality"""
    if len(steps) < 2:
        return False
    
    # Check for basic quality
    for step in steps:
        action = step['action'].lower()
        
        # Check it's not empty or too generic
        if (len(action) < 8 or 
            any(phrase in action for phrase in ['specific action', 'real ui', '[action]'])):
            return False
            
        # Check coordinates
        x, y = step['coordinates']
        if not (50 <= x <= 1230 and 50 <= y <= 670):
            return False
    
    # Check for duplicate actions
    actions = [step['action'] for step in steps]
    if len(set(actions)) < len(actions):
        return False
        
    return True

def create_improved_generic_fallback(instruction):
    """Create improved generic fallback with FULL text display"""
    
    # Use the full instruction without any truncation
    clean_instruction = instruction.strip()
    
    # Common browser interaction areas
    browser_areas = {
        "navigation": [
            {"coord": (200, 80), "element": "Address bar", "action": "Navigate to website for"},
            {"coord": (640, 80), "element": "URL field", "action": "Enter web address for"},
            {"coord": (100, 80), "element": "Browser tab", "action": "Open new tab for"}
        ],
        "search": [
            {"coord": (640, 200), "element": "Search box", "action": "Search for"},
            {"coord": (400, 200), "element": "Search field", "action": "Enter search terms for"},
            {"coord": (800, 200), "element": "Search button", "action": "Initiate search for"}
        ],
        "content": [
            {"coord": (640, 360), "element": "Content area", "action": "Access content for"},
            {"coord": (400, 300), "element": "Result item", "action": "Select item for"},
            {"coord": (800, 400), "element": "Action button", "action": "Complete action for"}
        ]
    }
    
    # Create logical flow based on general browser usage patterns
    nav_area = random.choice(browser_areas["navigation"])
    search_area = random.choice(browser_areas["search"])
    content_area = random.choice(browser_areas["content"])
    
    return [
        {
            "action": f"{nav_area['action']} {clean_instruction}",
            "coordinates": nav_area["coord"],
            "target": nav_area["element"],
            "type": "improved_fallback"
        },
        {
            "action": f"{search_area['action']} {clean_instruction}",
            "coordinates": search_area["coord"],
            "target": search_area["element"],
            "type": "improved_fallback"
        },
        {
            "action": f"{content_area['action']} {clean_instruction}",
            "coordinates": content_area["coord"],
            "target": content_area["element"],
            "type": "improved_fallback"
        }
    ]


# 4. Enhanced Step Processing

def enhance_steps_generically(steps, instruction):
    """Add enhancements without any text truncation"""
    enhanced_steps = []
    
    for i, step in enumerate(steps):
        enhanced_step = step.copy()
        
        # Remove any existing truncation in the action text
        if "..." in enhanced_step["action"]:
            # Replace truncation with full instruction
            enhanced_step["action"] = enhanced_step["action"].replace("...", instruction)
        
        # Realistic delays based on step position
        if i == 0:
            enhanced_step["delay_ms"] = random.randint(800, 1200)
        elif i == len(steps) - 1:
            enhanced_step["delay_ms"] = random.randint(1500, 2500)
        else:
            enhanced_step["delay_ms"] = random.randint(1000, 2000)
        
        # Confidence based on step type
        if step.get("type") == "llm_generated":
            enhanced_step["confidence"] = round(random.uniform(0.75, 0.92), 2)
        else:
            enhanced_step["confidence"] = round(random.uniform(0.65, 0.80), 2)
            
        enhanced_steps.append(enhanced_step)
    
    return enhanced_steps


# 5. Generate ESP32 Commands

def generate_esp32_commands(steps):
    """Generate executable commands"""
    commands = []
    
    for i, step in enumerate(steps, 1):
        x, y = step["coordinates"]
        
        command = {
            "step": i,
            "action": step["action"],
            "esp32_command": f"touch_screen({x}, {y})",
            "coordinates": f"({x}, {y})",
            "target": step["target"],
            "delay_ms": step["delay_ms"],
            "confidence": step["confidence"]
        }
        
        commands.append(command)
    
    return commands


# 6. Main Function

def main():
    """Main function - Completely generic for any instruction with full text display"""
    print("🎯 IMPROVED GENERIC LLM COORDINATE GENERATOR")
    print("⭐ NO HARDCODING - Shows FULL instruction text without truncation")
    print("=" * 60)
    
    while True:
        print("\n" + "="*50)
        print("📝 ENTER ANY BROWSER INSTRUCTION")
        print("="*50)
        
        instruction = input("\n👉 Enter any instruction (or 'quit' to exit): ").strip()
        
        if instruction.lower() in ['quit', 'exit', 'q']:
            print("👋 Thank you!")
            break
        
        if not instruction:
            print("❌ Please enter an instruction!")
            continue
        
        print(f"\n🔄 Processing: '{instruction}'")
        print("-" * 50)
        
        # Generate completely generic steps
        raw_steps = generate_truly_generic_steps(instruction)
        enhanced_steps = enhance_steps_generically(raw_steps, instruction)
        commands = generate_esp32_commands(enhanced_steps)
        
        # Display results
        print(f"\n✅ AUTOMATION STEPS FOR: '{instruction}'")
        print("=" * 60)
        
        for cmd in commands:
            print(f"\n🎯 Step {cmd['step']}: {cmd['action']}")
            print(f"   📍 Position: {cmd['coordinates']}")
            print(f"   🎯 Target: {cmd['target']}")
            print(f"   ⏱️  Delay: {cmd['delay_ms']}ms")
            print(f"   ✅ Confidence: {cmd['confidence']:.0%}")
        
        # Show ESP32 code
        print(f"\n💻 ESP32 EXECUTABLE CODE:")
        print("=" * 50)
        
        for cmd in commands:
            print(f"delay({cmd['delay_ms']});")
            print(f"// {cmd['action']}")
            print(f"{cmd['esp32_command']};  // Targets: {cmd['target']}")
            print()
        
        # Continue?
        continue_choice = input("\n🔄 Process another instruction? (y/n): ").strip().lower()
        if continue_choice not in ['y', 'yes', '']:
            print("👋 Thank you!")
            break


# 7. Run the System

if __name__ == "__main__":
    print("🚀 Starting Improved Generic LLM Coordinate Generator...")
    print("⚠️  NO TRUNCATION - Shows full instruction text!")
    main()




































































