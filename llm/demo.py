# generic_instruction_to_js_dataset.py
import json

# ----------------------------
# 1️⃣ Load Dataset
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

# ----------------------------
# 2️⃣ Generate JS Steps from Dataset
# ----------------------------
def generate_js_steps_from_dataset(instruction):
    """
    Look up instruction in dataset and return structured JS steps.
    """
    for entry in dataset:
        if entry["instruction"].lower() in instruction.lower():
            # Convert output string into structured steps
            steps_text = entry["output"].split("Step ")[1:]  # skip first empty split
            steps = []
            for s in steps_text:
                try:
                    num, rest = s.split(":", 1)
                    steps.append({
                        "step": int(num.strip()),
                        "action": rest.strip(),
                        "description": ""  # Can be filled with more info if available
                    })
                except ValueError:
                    # Fallback for unexpected formatting
                    steps.append({"step": 0, "action": s.strip(), "description": ""})
            return steps
    # Fallback if instruction not in dataset
    return [{"step": 1, "action": f"Do task: {instruction}", "description": "Fallback step"}]

# ----------------------------
# 3️⃣ Simulate sending steps to JS frontend
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
# 4️⃣ Main loop
# ----------------------------
def main():
    print("🚀 GENERIC INSTRUCTION TO JS (DATASET-DRIVEN)")
    print("=============================================")
    
    while True:
        instruction = input("\n💡 Enter any instruction (or 'quit' to exit): ").strip()
        
        if instruction.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
        
        if not instruction:
            print("❌ Please enter an instruction!")
            continue
        
        # Generate JS steps
        steps = generate_js_steps_from_dataset(instruction)
        
        # Display steps
        print(f"\n✅ STEPS FOR: '{instruction}'")
        print("=" * 40)
        for step in steps:
            print(f"\nStep {step['step']}: {step['action']}")
            if step['description']:
                print(f"   Description: {step['description']}")
        
        # Simulate sending steps
        print(f"\n📤 PASSING TO JS FRONTEND...")
        js_data = send_to_js(instruction, steps)
        
        # Show confirmation
        print(f"\n🎯 JS RECEIVED:")
        print(f"   Instruction: {js_data['instruction']}")
        print(f"   Steps: {js_data['total_steps']}")
        print(f"   Status: {js_data['status']}")
        
        # Continue?
        if input("\n🔄 Process another instruction? (y/n): ").lower() != 'y':
            print("👋 Thank you!")
            break

# ----------------------------
# 5️⃣ Run main
# ----------------------------
if __name__ == "__main__":
    main()




# # generic_instruction_to_esp32.py
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