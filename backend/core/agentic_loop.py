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


def run_cycle(start_delay: float = 4.0, stop_at_end: bool = True):
    logging.info("🔄 Starting Agentic AI full cycle...")

    # 1️⃣ Ensure vision is running (after a short delay)
    if start_delay and start_delay > 0:
        logging.info(f"⏳ Waiting {start_delay} seconds before starting vision...")
        time.sleep(start_delay)

    logging.info("📡 Step 1: Starting Vision")
    start_vision()

    # 2️⃣ Perceive
    logging.info("👁️ Step 2: Perceiving environment...")
    perception = perceive()
    logging.debug(f"Perception Output: {perception}")

    # 3️⃣ Plan
    logging.info("🧠 Step 3: Planning action...")
    action_plan = plan(perception)
    logging.debug(f"Generated Action Plan: {action_plan}")

    # 4️⃣ Act
    logging.info("🖱️ Step 4: Acting on plan...")
    action_result = act_with_retry(action_plan, max_retries=3)
    logging.debug(f"Action Result: {action_result}")

    # 5️⃣ Evaluate
    logging.info("📊 Step 5: Evaluating result...")
    evaluation = {
        "success": action_result.get("status") == "success"
    }
    logging.info(f"📊 Evaluation result: {evaluation}")

    # 6️⃣ Agent decides to stop vision (example condition)
    if action_plan.get("stop_vision", False):
        logging.info("⚠️ Action plan requested to stop vision.")
        stop_vision()

    # Optionally ensure vision is stopped at the end of the cycle
    if stop_at_end and not action_plan.get("stop_vision", False):
        logging.info("🔚 Stopping vision at end of cycle.")
        stop_vision()

    logging.info("✅ Cycle completed.")

    return {
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
