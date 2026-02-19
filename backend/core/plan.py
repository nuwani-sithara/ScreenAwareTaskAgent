# import logging
# from .llm_agent import generate_plan


# def plan(perception):
#     print("🧩 Planning next action (LangChain LLM)...")
#     logging.info(f"Planning next action based on perception: {perception}")
#     screen_text = perception.get("screen_text", "")

#     # generate_plan now returns a JSON-serializable dict (or a dict-like object)
#     action_json = generate_plan(screen_text)

#     # Ensure we return a dict
#     if not isinstance(action_json, dict):
#         logging.warning("LLM returned non-dict plan; wrapping into dict")
#         action_json = {"raw_plan": str(action_json)}

#     logging.info(f"Plan result (JSON): {action_json}")
#     print(f"🤖 LLM Plan (JSON): {action_json}")
#     return action_json


import logging
from .llm_agent import generate_plan


def plan(perception, user_task: str):
    """
    Generate an action plan using:
    - User task (mandatory)
    - Perception data (optional, may be None)
    """

    print("🧩 Planning next action (LangChain LLM)...")
    logging.info("🧠 Planning phase started")

    # --------------------------------------
    # Extract screen text safely
    # --------------------------------------
    screen_text = ""

    if perception and isinstance(perception, dict):
        screen_text = perception.get("screen_text", "")
        logging.info("👁️ Using perception data for planning")
    else:
        logging.info("🚫 No perception data provided (vision skipped)")

    # --------------------------------------
    # Construct structured LLM input
    # --------------------------------------
    structured_prompt = f"""
You are an AI automation agent.

User Task:
{user_task}

Screen Text (OCR Output):
{screen_text if screen_text else "No screen data available"}

Instructions:
- Decide the next best action.
- Return ONLY valid JSON.
- Format:
{{
    "action": "<click/type/scroll/wait/etc>",
    "target": "<UI element or description>",
    "stop_vision": false
}}
"""

    logging.info(f"📨 LLM Prompt:\n{structured_prompt}")

    # --------------------------------------
    # Call LLM
    # --------------------------------------
    action_json = generate_plan(user_task)

    # --------------------------------------
    # Safety: Ensure dict output
    # --------------------------------------
    if not isinstance(action_json, dict):
        logging.warning("⚠️ LLM returned non-dict plan; wrapping into dict")
        action_json = {"raw_plan": str(action_json)}

    logging.info(f"✅ Plan result (JSON): {action_json}")
    print(f"🤖 LLM Plan (JSON): {action_json}")

    return action_json