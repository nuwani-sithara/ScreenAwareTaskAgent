import logging
from core.llm_agent import generate_plan


def plan(perception):
    print("🧩 Planning next action (LangChain LLM)...")
    logging.info(f"Planning next action based on perception: {perception}")
    screen_text = perception.get("screen_text", "")

    # generate_plan now returns a JSON-serializable dict (or a dict-like object)
    action_json = generate_plan(screen_text)

    # Ensure we return a dict
    if not isinstance(action_json, dict):
        logging.warning("LLM returned non-dict plan; wrapping into dict")
        action_json = {"raw_plan": str(action_json)}

    logging.info(f"Plan result (JSON): {action_json}")
    print(f"🤖 LLM Plan (JSON): {action_json}")
    return action_json

