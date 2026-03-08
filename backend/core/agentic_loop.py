import requests
import logging
import time

from backend.core.perceive import perceive, stream_vision
from backend.core.plan import plan
from backend.core.act import act_with_retry
from vision.src import perception
import json
from backend.utils.file_utils import create_run_folder, save_json
from plyer import notification

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


def show_popup(title, message):
    notification.notify(
        title=title,
        message=message,
        timeout=5
    )

def start_vision():
    logging.info("➡️ Sending request to START vision service with parameters...")
    try:
        response = requests.post(
            f"{VISION_BASE_URL}/vision/start",
            params={
                "camera_index": 1,
                "save_interval": 1,
                "provider": "gemini",
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

        response = requests.post(STOP_VISION_URL, timeout=360)

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
        "login", "form", "field", "image", "photo", "visual", "interface", "page", "app","type","ask", "enter"
    ]

    needs_vision = any(keyword in task_lower for keyword in vision_keywords)

    logging.info(f"👁️ Vision required: {needs_vision}")

    return needs_vision


def compare_screens(baseline, latest):
    """
    Compare baseline and latest screen(s). Returns a text summary of differences.
    """
    if not baseline or not latest:
        return "No screen data available to compare."

    # Only compare the first baseline vs first latest screen for simplicity
    base_elements = baseline.get("elements", [])
    latest_elements = latest[0].get("elements", [])

    # Use (type, label) as the identity of an element
    base_ids = set((el.get("type"), el.get("label")) for el in base_elements)
    latest_ids = set((el.get("type"), el.get("label")) for el in latest_elements)

    added = latest_ids - base_ids
    removed = base_ids - latest_ids

    messages = []

    if added:
        messages.append(
            "New elements appeared: " + ", ".join(f"{typ}('{lbl}')" for typ, lbl in added)
        )
    if removed:
        messages.append(
            "Elements disappeared: " + ", ".join(f"{typ}('{lbl}')" for typ, lbl in removed)
        )
    if not messages:
        messages.append("No significant screen changes detected.")

    return "\n".join(messages)

def run_cycle(user_task: str, start_delay: float = 2.0, stop_at_end: bool = True):
    run_folder = create_run_folder()
    logging.info(f"📁 Created run folder: {run_folder}")

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
        save_json(perception, "perception", run_folder)
        logging.info(f"📦 Session ID: {perception.get('session_id')}")
        screens = perception.get("session_data", {}).get("screens", [])
        logging.info("🖼 Screens:\n%s", json.dumps(screens, indent=2))
       
        # Save first screen as baseline for comparison later
        baseline_screen = screens[0] if screens else None

        logging.info(f"📌 Baseline screen captured: {json.dumps(baseline_screen, indent=2)}")

        vision_end_time = time.time()
        logging.info(
            f"⏱️ TOTAL Vision Cycle Time: {vision_end_time - vision_start_time:.2f}s"
        )
       
    else:
        logging.info("🚫 Vision not required for this task. Skipping perception.")

    # 3️⃣ Plan (Pass perception OR None)
    logging.info("🧠 Planning action...")
    action_plan = plan(user_task=user_task, perception=perception)
    save_json(action_plan, "action_plan", run_folder)
    logging.info(
        "Generated Action Plan:\n%s",
        json.dumps(action_plan, indent=2)
    )

    validation = action_plan.get("validation", {})

    if not validation.get("is_valid", True):

        return {
            "status": "needs_input",
            "missing_fields": validation.get("missing_elements", []),
            "message": validation.get("reason")
        }

    # 4️⃣ Act
    logging.info("🖱️ Acting on plan...")
    action_result = act_with_retry(action_plan, max_retries=3)
    save_json(action_result, "action_result", run_folder)
    logging.debug(f"Action Result: {action_result}")

    latest_perception = None
    latest_screens = []

    if use_vision:
        logging.info("📡 Capturing latest screen visuals after action...")
        start_vision()
        latest_perception = stop_vision()  # stop vision to get final frame
        save_json(latest_perception, "latest_perception", run_folder)

        latest_screens = latest_perception.get("session_data", {}).get("screens", [])
        logging.info(f"🖼 Latest Screens Captured:\n{json.dumps(latest_screens, indent=2)}")

    screen_change_msg = compare_screens(baseline_screen, latest_screens)

    logging.info(f"🔄 Screen Change Summary:\n{screen_change_msg}")
        
    # 5️⃣ Evaluate
    logging.info("📊 Evaluating result...")
    success = action_result.get("status") == "success"

    evaluation = {
        "success": success
    }

    logging.info(f"📊 Evaluation result: {evaluation}")

    # --- POPUP MESSAGE ---
    if success:
        show_popup(
            "Testing Completed",
            "Testing is successfully done. Please check your chatbot for the result."
        )
    else:
        reason = action_result.get("reason", "Unknown error")

        show_popup(
            "Testing Failed",
            f"Testing failed due to: {reason}"
        )

    logging.info("✅ Cycle completed.")

    full_cycle_end_time = time.time()

    logging.info(
        f"⏱️ FULL AGENT CYCLE TIME: {full_cycle_end_time - full_cycle_start_time:.2f}s"
    )

    final_output = {
    "vision_used": use_vision,
    "perception": perception,
    "latest_perception": latest_perception,
    "action_plan": action_plan,
    "action_result": action_result,
    "evaluation": evaluation,
    "screen_change_message": screen_change_msg  # <-- pass this
    }

    save_json(final_output, "full_cycle", run_folder)

    return final_output

# def run_cycle(user_task: str, context: dict | None = None):

#     logging.info(f"🔄 Starting Agent cycle for task: {user_task}")

#     # 1️⃣ Validate requirements
#     validation = validate_task_requirements(user_task, context)

#     if validation["need_input"]:
#         logging.info("⚠️ Missing user input")

#         return question(
#             validation["question"],
#             validation.get("fields")
#         )

#     # 2️⃣ Decide vision usage
#     use_vision = should_use_vision(user_task)

#     perception = None

#     if use_vision:
#         logging.info("📡 Starting vision service")

#         start_vision()

#         perception = stop_vision()

#         if not perception:
#             return error(
#                 "Vision system did not capture any screens. Please open the application UI and try again."
#             )

#     # 3️⃣ Plan
#     logging.info("🧠 Planning action")

#     action_plan = plan(user_task=user_task, perception=perception)

#     if not action_plan:
#         return error("Unable to generate an action plan for this task.")

#     # 4️⃣ Act
#     logging.info("🖱 Executing action")

#     action_result = act_with_retry(action_plan, max_retries=3)

#     # 5️⃣ Evaluate
#     success = action_result.get("status") == "success"

#     summary = {
#         "steps_passed": 1 if success else 0,
#         "steps_failed": 0 if success else 1,
#         "errors": [] if success else ["UI interaction failed"]
#     }

#     if success:

#         message = f"""
# ✅ Test completed successfully

# Steps performed:
# • Action: {action_plan.get('action')}
# • Target: {action_plan.get('target')}

# No blocking issues detected.
# """

#         return result(message, summary)

#     else:

#         message = f"""
# ❌ Test failed

# Attempted action:
# • {action_plan.get('action')}

# Target:
# • {action_plan.get('target')}

# Possible issue:
# • Element not clickable
# • UI changed
# """

#         return result(message, summary)

# import requests
# import logging
# import time

# from backend.core.perceive import perceive, stream_vision
# from backend.core.plan import plan
# from backend.core.act import act_with_retry
# from vision.src import perception
# import json

# # --- Logging Setup ---
# logging.basicConfig(
#     filename="agentic_ai_log.txt",
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)s | %(message)s",
# )

# logger = logging.getLogger(__name__)

# logger.info("=== Agentic AI System Started ===")

# logging.basicConfig(level=logging.INFO)

# VISION_BASE_URL = "http://localhost:8001"
# LLM_BASE_URL = "http://localhost:8002"  # LLM FastAPI service
# VISION_AUTO_STOP_DELAY = 120 
# STOP_VISION_URL = "http://localhost:8001/vision/stop"

# def start_vision():
#     logging.info("➡️ Sending request to START vision service with parameters...")
#     try:
#         response = requests.post(
#             f"{VISION_BASE_URL}/vision/start",
#             params={
#                 "camera_index": 1,
#                 "save_interval": 1,
#                 "provider": "gemini",
#                 "local_model": "llava:7b",
#                 "ollama_timeout_seconds": 60
#             }
#         )
#         logging.info(f"✅ Vision start response status: {response.status_code}")
#         logging.info(f"📨 Vision start response body: {response.text}")
#     except Exception as e:
#         logging.error(f"❌ Failed to start vision service: {e}")

# def stop_vision():
#     logging.info("➡️ Sending request to STOP vision service...")

#     try:
#         start_time = time.time()

#         response = requests.post(STOP_VISION_URL, timeout=300)

#         end_time = time.time()
#         logging.info(f"⏱️ Vision STOP Response Time: {end_time - start_time:.2f}s")

#         response.raise_for_status()
#         data = response.json()

#         logging.info(f"🛑 Vision stop response status: {response.status_code}")
#         logging.info(f"📦 Vision stop session_id: {data.get('session_id')}")

#         return data

#     except Exception as e:
#         logging.error(f"❌ Failed to stop vision service: {e}")
#         return {"error": "vision_stop_failed", "detail": str(e)}
    
    
# def should_use_vision(user_task: str) -> bool:
#     """
#     Decide whether the task requires visual perception.
#     Later this can be replaced with LLM reasoning.
#     """

#     logging.info("🤔 Deciding whether vision is required for this task...")

#     task_lower = user_task.lower()

#     # Simple rule-based decision (upgrade later with LLM)
#     vision_keywords = [
#         "click", "open", "check ui", "validate",
#         "verify", "see", "screen", "button",
#         "login", "form", "field", "image", "photo", "visual", "interface", "page", "app","type"
#     ]

#     needs_vision = any(keyword in task_lower for keyword in vision_keywords)

#     logging.info(f"👁️ Vision required: {needs_vision}")

#     return needs_vision

# def execute_with_visual_validation(action_plan, user_task):
#     """
#     Execute each action step-by-step.
#     After critical steps (like type_text or click),
#     re-run vision and validate UI change.
#     """

#     hid_commands = action_plan.get("hid_commands", [])
#     action_steps = action_plan.get("action_steps", [])

#     if not hid_commands:
#         return {"status": "no_commands"}

#     for index, command in enumerate(hid_commands):

#         # 1️⃣ Execute single command
#         single_plan = {"hid_commands": [command]}
#         result = act_with_retry(single_plan, max_retries=2)

#         if result.get("status") != "success":
#             return {"status": "failed", "failed_command": command}

#         # 2️⃣ Only validate after meaningful actions
#         if command["cmd"] in ["type_text", "mouse_click"]:

#             logging.info("🔍 Re-perceiving screen for validation...")

#             # Short delay to allow UI update
#             time.sleep(1.5)

#             start_vision()
#             new_perception = stop_vision()

#             validation_success = validate_step(
#                 command,
#                 new_perception
#             )

#             if not validation_success:
#                 logging.warning("⚠️ Step validation failed. Retrying...")

#                 retry_result = act_with_retry(single_plan, max_retries=1)

#                 if retry_result.get("status") != "success":
#                     return {
#                         "status": "validation_failed",
#                         "failed_command": command
#                     }

#     return {"status": "success"}

# def validate_step(command, perception):
#     """
#     Validate if the expected UI change happened.
#     """

#     screens = perception.get("session_data", {}).get("screens", [])

#     if not screens:
#         return False

#     latest_screen = screens[-1]
#     elements = latest_screen.get("elements", [])

#     # If typing text → check if text appears in OCR labels
#     if command["cmd"] == "type_text":
#         expected_text = command.get("text", "").lower()

#         for elem in elements:
#             label = (elem.get("label") or "").lower()
#             if expected_text in label:
#                 logging.info("✅ Typed text found in screen.")
#                 return True

#         logging.warning("❌ Typed text not found in screen.")
#         return False

#     # If clicking login → check if screen changed
#     if command["cmd"] == "mouse_click":
#         logging.info("🖱️ Click performed. Assuming UI may change.")
#         return True  # Improve later with hash comparison

#     return True


# def run_cycle(user_task: str, start_delay: float = 2.0, stop_at_end: bool = True):
#     full_cycle_start_time = time.time()
#     logging.info(f"🔄 Starting Agentic AI full cycle for task: '{user_task}'")

#     # 1️⃣ Decide if vision is required
#     use_vision = should_use_vision(user_task)

#     perception = None

#     vision_start_time = time.time()
#     # 2️⃣ Start Vision only if needed
#     if use_vision:
#         if start_delay and start_delay > 0:
#             logging.info(f"⏳ Waiting {start_delay} seconds before starting vision...")
#             time.sleep(start_delay)

#         logging.info("📡 Vision required. Starting vision service...")
#         start_vision()

#         logging.info("⏳ Vision will auto-stop after 6 minutes (360 seconds).")

#         # # Auto stop after 6 minutes
#         # logging.info("⏳ Waiting 6 minutes before stopping vision...")
#         # time.sleep(VISION_AUTO_STOP_DELAY)

#         logging.info("⏹️ Auto-stopping vision after 6 minutes.")
#         perception = stop_vision()
#         logging.info(f"📦 Session ID: {perception.get('session_id')}")
#         screens = perception.get("session_data", {}).get("screens", [])
#         logging.info("🖼 Screens:\n%s", json.dumps(screens, indent=2))

#         vision_end_time = time.time()
#         logging.info(
#             f"⏱️ TOTAL Vision Cycle Time: {vision_end_time - vision_start_time:.2f}s"
#         )
       
#     else:
#         logging.info("🚫 Vision not required for this task. Skipping perception.")

#     # 3️⃣ Plan (Pass perception OR None)
#     logging.info("🧠 Planning action...")
#     action_plan = plan(user_task=user_task, perception=perception)
#     logging.info(
#         "Generated Action Plan:\n%s",
#         json.dumps(action_plan, indent=2)
#     )

#     # 4️⃣ Act
#     logging.info("🖱️ Acting on plan...")
#     action_result = execute_with_visual_validation(action_plan,user_task)
#     logging.debug(f"Action Result: {action_result}")

#     # 5️⃣ Evaluate
#     logging.info("📊 Evaluating result...")
#     evaluation = {
#         "success": action_result.get("status") == "success"
#     }

#     logging.info(f"📊 Evaluation result: {evaluation}")

#     logging.info("✅ Cycle completed.")

#     full_cycle_end_time = time.time()

#     logging.info(
#         f"⏱️ FULL AGENT CYCLE TIME: {full_cycle_end_time - full_cycle_start_time:.2f}s"
#     )

#     return {
#         "vision_used": use_vision,
#         "perception": perception,
#         "action_plan": action_plan,
#         "action_result": action_result,
#         "evaluation": evaluation
#     }

