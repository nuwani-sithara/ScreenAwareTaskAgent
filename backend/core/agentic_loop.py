# import requests
# import logging
# import time

# from backend.core.perceive import perceive, stream_vision
# from backend.core.plan import plan
# from backend.core.act import act_with_retry

# VISION_BASE_URL = "http://localhost:8001"
# LLM_BASE_URL = "http://localhost:8002"  # LLM FastAPI service

# def start_vision():
#     logging.info("Starting Vision capture loop...")
#     requests.post(f"{VISION_BASE_URL}/vision/start")
 
# def stop_vision():
#     logging.info("Stopping Vision capture loop...")
#     requests.post(f"{VISION_BASE_URL}/vision/stop")
 
# def run_cycle(start_delay: float = 4.0, stop_at_end: bool = True):
#     # 1️⃣ Ensure vision is running (after a short delay)
#     if start_delay and start_delay > 0:
#         time.sleep(start_delay)
#     start_vision()
 
#     # 2️⃣ Perceive
#     perception = perceive()
 
#     # 3️⃣ Plan
#     action_plan = plan(perception)
 
#     # 4️⃣ Act
#     action_result = act_with_retry(action_plan, max_retries=3)
 
#     # 5️⃣ Evaluate
#     evaluation = {
#         "success": action_result.get("status") == "success"
#     }
 
#     logging.info(f"📊 Evaluation result: {evaluation}")
 
#     # 6️⃣ Agent decides to stop vision (example condition)
#     if action_plan.get("stop_vision", False):
#         stop_vision()
 
#     # Optionally ensure vision is stopped at the end of the cycle
#     if stop_at_end and not action_plan.get("stop_vision", False):
#         stop_vision()
 
#     return {
#         "perception": perception,
#         "action_plan": action_plan,
#         "action_result": action_result,
#         "evaluation": evaluation
#     }


# def run_streaming_cycle(max_events: int = 10):
#     """Start vision capture and process incoming per-frame perception results in a loop.

#     For each received `vision_data`, run planning and acting immediately. Stops early if
#     an action_plan contains `stop_vision`.
#     """
#     logging.info("Starting streaming cycle...")
#     start_vision()

#     results = []
#     try:
#         for item in stream_vision(max_events=max_events):
#             if not isinstance(item, dict):
#                 continue
#             if item.get("error"):
#                 logging.warning(f"Received stream error: {item}")
#                 continue
#             vision_data = item.get("vision_data") or item
#             action_plan = plan(vision_data)
#             action_result = act_with_retry(action_plan, max_retries=3)

#             results.append({
#                 "perception": vision_data,
#                 "action_plan": action_plan,
#                 "action_result": action_result
#             })

#             if action_plan.get("stop_vision", False):
#                 logging.info("Action requested to stop vision. Stopping.")
#                 stop_vision()
#                 break

#     finally:
#         # Ensure vision is stopped
#         stop_vision()

#     return results



import requests
import logging
import time

from backend.core.perceive import perceive, stream_vision
from backend.core.plan import plan
from backend.core.act import act_with_retry

logging.basicConfig(level=logging.INFO)

VISION_BASE_URL = "http://localhost:8001"
LLM_BASE_URL = "http://localhost:8002"  # LLM FastAPI service


def start_vision():
    logging.info("➡️ Sending request to START vision service...")
    try:
        response = requests.post(f"{VISION_BASE_URL}/vision/start")
        logging.info(f"✅ Vision start response status: {response.status_code}")
    except Exception as e:
        logging.error(f"❌ Failed to start vision service: {e}")


def stop_vision():
    logging.info("➡️ Sending request to STOP vision service...")
    try:
        response = requests.post(f"{VISION_BASE_URL}/vision/stop")
        logging.info(f"🛑 Vision stop response status: {response.status_code}")
    except Exception as e:
        logging.error(f"❌ Failed to stop vision service: {e}")

def should_use_vision(user_task: str) -> bool:
    """
    Decide whether the task requires visual perception.
    Later this can be replaced with LLM reasoning.
    """

    logging.info("🤔 Deciding whether vision is required for this task...")

    task_lower = user_task.lower()

    # Simple rule-based decision (upgrade later with LLM)
    vision_keywords = [
        "click", "open", "check ui", "validate",
        "verify", "see", "screen", "button",
        "login", "form", "field", "image", "photo", "visual", "interface", "page", "app"
    ]

    needs_vision = any(keyword in task_lower for keyword in vision_keywords)

    logging.info(f"👁️ Vision required: {needs_vision}")

    return needs_vision


def run_cycle(user_task: str, start_delay: float = 2.0, stop_at_end: bool = True):
    logging.info(f"🔄 Starting Agentic AI full cycle for task: '{user_task}'")

    # 1️⃣ Decide if vision is required
    use_vision = should_use_vision(user_task)

    perception = None

    # 2️⃣ Start Vision only if needed
    if use_vision:
        if start_delay and start_delay > 0:
            logging.info(f"⏳ Waiting {start_delay} seconds before starting vision...")
            time.sleep(start_delay)

        logging.info("📡 Vision required. Starting vision service...")
        start_vision()

        logging.info("👁️ Perceiving environment...")
        perception = perceive()
        logging.debug(f"Perception Output: {perception}")

    else:
        logging.info("🚫 Vision not required for this task. Skipping perception.")

    # 3️⃣ Plan (Pass perception OR None)
    logging.info("🧠 Planning action...")
    action_plan = plan(perception, user_task=user_task)
    logging.debug(f"Generated Action Plan: {action_plan}")

    # 4️⃣ Act
    logging.info("🖱️ Acting on plan...")
    action_result = act_with_retry(action_plan, max_retries=3)
    logging.debug(f"Action Result: {action_result}")

    # 5️⃣ Evaluate
    logging.info("📊 Evaluating result...")
    evaluation = {
        "success": action_result.get("status") == "success"
    }

    logging.info(f"📊 Evaluation result: {evaluation}")

    # 6️⃣ Stop vision only if it was started
    if use_vision and stop_at_end:
        logging.info("🔚 Stopping vision at end of cycle.")
        stop_vision()

    logging.info("✅ Cycle completed.")

    return {
        "vision_used": use_vision,
        "perception": perception,
        "action_plan": action_plan,
        "action_result": action_result,
        "evaluation": evaluation
    }


def run_streaming_cycle(max_events: int = 10):
    """Start vision capture and process incoming per-frame perception results in a loop.
    For each received `vision_data`, run planning and acting immediately.
    Stops early if an action_plan contains `stop_vision`.
    """
    logging.info("🚀 Starting streaming Agentic AI cycle...")
    logging.info(f"🎥 Max events allowed: {max_events}")

    start_vision()

    results = []
    event_counter = 0

    try:
        for item in stream_vision(max_events=max_events):
            logging.info(f"📥 Received stream item #{event_counter + 1}")

            if not isinstance(item, dict):
                logging.warning("⚠️ Skipping non-dictionary stream item.")
                continue

            if item.get("error"):
                logging.warning(f"⚠️ Stream returned error: {item}")
                continue

            vision_data = item.get("vision_data") or item
            logging.debug(f"👁️ Vision Data: {vision_data}")

            logging.info("🧠 Planning action from vision data...")
            action_plan = plan(vision_data)
            logging.debug(f"Generated Action Plan: {action_plan}")

            logging.info("🖱️ Executing action plan with retry logic...")
            action_result = act_with_retry(action_plan, max_retries=3)
            logging.debug(f"Action Result: {action_result}")

            results.append({
                "perception": vision_data,
                "action_plan": action_plan,
                "action_result": action_result
            })

            event_counter += 1

            if action_plan.get("stop_vision", False):
                logging.info("🛑 Action requested to stop vision. Stopping stream.")
                stop_vision()
                break

    except Exception as e:
        logging.error(f"❌ Error during streaming cycle: {e}")

    finally:
        logging.info("🔚 Ensuring vision is stopped...")
        stop_vision()

    logging.info("✅ Streaming cycle completed.")
    return results