import requests
import logging
import json
import time

LLM_BASE_URL = "http://localhost:8002"

def plan(user_task: str, perception=None, model: str = "models/gemini-flash-latest"):
    """
    Generate HID action plan using LLM visual reasoning.

    Args:
        user_task (str): Natural language instruction
        perception (dict): Full perception JSON from vision stop()
        model (str): LLM model name

    Returns:
        dict: Action plan containing HID commands
    """

    logging.info("🧠 Planner started...")

    # 🔹 If task does NOT require vision
    if perception is None:
        logging.info("📭 No perception provided. Using text-only planning.")

        return {
            "status": "no_vision",
            "instruction": user_task,
            "hid_commands": [],
            "message": "Vision not used for this task"
        }

    try:
        visual_data = perception.get("session_data", {})

        payload = {
            "instruction": user_task,
            "visual_data": {
                "session_data": visual_data
            },
            "use_gemini": True,
            "gemini_model": model,
            "skip_validation": False
        }

        logging.info("📡 Sending request to LLM /generate_hid...")
        logging.debug("LLM Payload:\n%s", json.dumps(payload, indent=2))

    # ⏱ Measure request time
        start_time = time.time()
        response = requests.post(
            f"{LLM_BASE_URL}/llm/generate_hid",
            json=payload,
            timeout=360  # increased timeout
        )
        end_time = time.time()
        logging.info(f"⏱️ LLM Response Time: {end_time - start_time:.2f}s")
        

        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            logging.error("❌ LLM returned error response: %s", data)
            return {
                "status": "error",
                "error": data
            }

        logging.info("✅ HID plan generated successfully")
        logging.info(f"🎯 Total Commands: {data.get('total_commands')}")

        return {
            "status": data.get("status"),
            "instruction": data.get("instruction"),
            "validation": data.get("validation"),
            "rewritten_steps": data.get("rewritten_steps", []),
            "action_steps": data.get("action_steps", []),
            "hid_commands": data.get("hid_commands", []),
            "total_commands": data.get("total_commands", 0),
            "timestamp": data.get("timestamp"),
            "execution_time": data.get("execution_time"),
        }

    except requests.RequestException as e:
        logging.error(f"❌ Failed to contact LLM service: {e}")
        return {
            "status": "llm_unreachable",
            "error": str(e)
        }

    except Exception as e:
        logging.exception("❌ Planner crashed")
        return {
            "status": "planner_error",
            "error": str(e)
        }