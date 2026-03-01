import requests
import logging
import time

from backend.core.perceive import perceive, stream_vision
from backend.core.plan import plan
from backend.core.act import act_with_retry
from vision.src import perception
import json

# --- Logging Setup ---
logging.basicConfig(
    filename="agentic_ai_log.txt",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

logger.info("=== Agentic AI System Started ===")

logging.basicConfig(level=logging.INFO)

VISION_BASE_URL = "http://localhost:8001"
LLM_BASE_URL = "http://localhost:8002"  # LLM FastAPI service
VISION_AUTO_STOP_DELAY = 120 
STOP_VISION_URL = "http://localhost:8001/vision/stop"

def start_vision():
    logging.info("➡️ Sending request to START vision service with parameters...")
    try:
        response = requests.post(
            f"{VISION_BASE_URL}/vision/start",
            params={
                "camera_index": 1,
                "save_interval": 1,
                "provider": "ollama",
                "local_model": "llava:7b",
                "ollama_timeout_seconds": 60
            }
        )
        logging.info(f"✅ Vision start response status: {response.status_code}")
        logging.info(f"📨 Vision start response body: {response.text}")
    except Exception as e:
        logging.error(f"❌ Failed to start vision service: {e}")

def stop_vision():
    logging.info("➡️ Sending request to STOP vision service...")

    try:
        start_time = time.time()

        response = requests.post(STOP_VISION_URL, timeout=300)

        end_time = time.time()
        logging.info(f"⏱️ Vision STOP Response Time: {end_time - start_time:.2f}s")

        response.raise_for_status()
        data = response.json()

        logging.info(f"🛑 Vision stop response status: {response.status_code}")
        logging.info(f"📦 Vision stop session_id: {data.get('session_id')}")

        return data

    except Exception as e:
        logging.error(f"❌ Failed to stop vision service: {e}")
        return {"error": "vision_stop_failed", "detail": str(e)}
    
    
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
        "login", "form", "field", "image", "photo", "visual", "interface", "page", "app","type"
    ]

    needs_vision = any(keyword in task_lower for keyword in vision_keywords)

    logging.info(f"👁️ Vision required: {needs_vision}")

    return needs_vision


def run_cycle(user_task: str, start_delay: float = 2.0, stop_at_end: bool = True):
    full_cycle_start_time = time.time()
    logging.info(f"🔄 Starting Agentic AI full cycle for task: '{user_task}'")

    # 1️⃣ Decide if vision is required
    use_vision = should_use_vision(user_task)

    perception = None

    vision_start_time = time.time()
    # 2️⃣ Start Vision only if needed
    if use_vision:
        if start_delay and start_delay > 0:
            logging.info(f"⏳ Waiting {start_delay} seconds before starting vision...")
            time.sleep(start_delay)

        logging.info("📡 Vision required. Starting vision service...")
        start_vision()

        logging.info("⏳ Vision will auto-stop after 6 minutes (360 seconds).")

        # # Auto stop after 6 minutes
        # logging.info("⏳ Waiting 6 minutes before stopping vision...")
        # time.sleep(VISION_AUTO_STOP_DELAY)

        logging.info("⏹️ Auto-stopping vision after 6 minutes.")
        perception = stop_vision()
        logging.info(f"📦 Session ID: {perception.get('session_id')}")
        screens = perception.get("session_data", {}).get("screens", [])
        logging.info("🖼 Screens:\n%s", json.dumps(screens, indent=2))

        vision_end_time = time.time()
        logging.info(
            f"⏱️ TOTAL Vision Cycle Time: {vision_end_time - vision_start_time:.2f}s"
        )
       
    else:
        logging.info("🚫 Vision not required for this task. Skipping perception.")

    # 3️⃣ Plan (Pass perception OR None)
    logging.info("🧠 Planning action...")
    action_plan = plan(user_task=user_task, perception=perception)
    logging.info(
        "Generated Action Plan:\n%s",
        json.dumps(action_plan, indent=2)
    )

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

    logging.info("✅ Cycle completed.")

    full_cycle_end_time = time.time()

    logging.info(
        f"⏱️ FULL AGENT CYCLE TIME: {full_cycle_end_time - full_cycle_start_time:.2f}s"
    )

    return {
        "vision_used": use_vision,
        "perception": perception,
        "action_plan": action_plan,
        "action_result": action_result,
        "evaluation": evaluation
    }


# def run_streaming_cycle(user_task: str, max_events: int = 10):
#     """Start vision capture and process incoming per-frame perception results in a loop.
#     For each received `vision_data`, run planning and acting immediately.
#     Stops early if an action_plan contains `stop_vision`.
#     """
#     logging.info(f"🚀 Starting streaming Agentic AI cycle for task: '{user_task}'")
#     logging.info(f"🎥 Max events allowed: {max_events}")

#     start_vision()

#     results = []
#     event_counter = 0

#     try:
#         for item in stream_vision(max_events=max_events):
#             logging.info(f"📥 Received stream item #{event_counter + 1}")

#             if not isinstance(item, dict):
#                 logging.warning("⚠️ Skipping non-dictionary stream item.")
#                 continue

#             if item.get("error"):
#                 logging.warning(f"⚠️ Stream returned error: {item}")
#                 continue

#             vision_data = item.get("vision_data") or item
#             logging.debug(f"👁️ Vision Data: {vision_data}")

#             logging.info("🧠 Planning action from vision data...")
#             action_plan = plan(vision_data, user_task=user_task)
#             logging.debug(f"Generated Action Plan: {action_plan}")

#             logging.info("🖱️ Executing action plan with retry logic...")
#             action_result = act_with_retry(action_plan, max_retries=3)
#             logging.debug(f"Action Result: {action_result}")

#             results.append({
#                 "perception": vision_data,
#                 "action_plan": action_plan,
#                 "action_result": action_result
#             })

#             event_counter += 1

#             if action_plan.get("stop_vision", False):
#                 logging.info("🛑 Action requested to stop vision. Stopping stream.")
#                 stop_vision()
#                 break

#     except Exception as e:
#         logging.error(f"❌ Error during streaming cycle: {e}")

#     finally:
#         logging.info("🔚 Ensuring vision is stopped...")
#         stop_vision()

#     logging.info("✅ Streaming cycle completed.")
#     return results