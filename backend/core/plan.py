import logging
from backend.core.llm_agent import generate_plan

def plan(perception):
    print("🧩 Planning next action (LangChain LLM)...")
    logging.info(f"Planning next action based on perception: {perception}")
    screen_text = perception.get("screen_text", "")
    action_str = generate_plan(screen_text)
    
    # Convert string plan to JSON format for HID
    action_json = {
        "action": "click",  # simplified mock mapping
        "target": action_str  # could parse LLM result more intelligently later
    }

    logging.info(f"Plan result (JSON): {action_json}")
    print(f"🤖 LLM Plan (JSON): {action_json}")
    return action_json

