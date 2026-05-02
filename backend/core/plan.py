import requests
import logging
import json
import time

LLM_BASE_URL = "http://localhost:8002"


def _remap_coordinate_payload(payload):
    if isinstance(payload, list):
        return [_remap_coordinate_payload(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    remapped = {}
    for key, value in payload.items():
        if key in ("elements", "current_elements", "resolved_elements") and isinstance(value, list):
            remapped[key] = [_remap_element_coords(elem) for elem in value]
        else:
            remapped[key] = _remap_coordinate_payload(value)
    return remapped


def _remap_element_coords(elem):
    if not isinstance(elem, dict):
        return elem

    new_elem = dict(elem)
    frame_dx = new_elem.get("frame_dx")
    frame_dy = new_elem.get("frame_dy")
    if frame_dx is not None:
        try:
            new_elem["dx"] = int(round(float(frame_dx)))
        except Exception:
            pass
    if frame_dy is not None:
        try:
            new_elem["dy"] = int(round(float(frame_dy)))
        except Exception:
            pass

    bbox = new_elem.get("bbox")
    if ("dx" not in new_elem or "dy" not in new_elem) and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            x1, y1, x2, y2 = (float(v) for v in bbox)
            new_elem["dx"] = int(round((x1 + x2) * 0.5))
            new_elem["dy"] = int(round((y1 + y2) * 0.5))
        except Exception:
            pass

    return new_elem

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
        knowledge_base = visual_data.get("knowledge_base") if isinstance(visual_data, dict) else None
        latest_resolved_elements = []
        if isinstance(knowledge_base, dict):
            latest_resolved_elements = knowledge_base.get("resolved_elements") or []
        if not latest_resolved_elements and isinstance(visual_data, dict):
            screens = visual_data.get("screens", [])
            if screens:
                latest_screen = screens[-1] if isinstance(screens[-1], dict) else {}
                latest_resolved_elements = latest_screen.get("elements", []) if isinstance(latest_screen, dict) else []

        payload = {
            "instruction": user_task,
            "visual_data": {
                "session_data": _remap_coordinate_payload(visual_data),
                "session_memory": knowledge_base,
                "resolved_elements": _remap_coordinate_payload(latest_resolved_elements),
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
