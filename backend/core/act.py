from backend.core.hid_mock import send_hid_command
import logging

def act(action_plan_json: dict):
    """
    Act function that forwards JSON action to the dummy HID.
    """
    logging.info(f"Acting on JSON plan: {action_plan_json}")
    print(f"🖱️ Acting on: {action_plan_json}")

    # Forward to dummy HID
    result = send_hid_command(action_plan_json)

    logging.info(f"Action result: {result}")
    return result


def act_with_retry(action_plan_json: dict, max_retries: int = 3):
    """
    Retry mechanism for act function.
    Tries up to max_retries if action fails.
    """
    for attempt in range(1, max_retries + 1):
        result = act(action_plan_json)
        if result.get("status") == "success":
            print(f"✅ Action succeeded on attempt {attempt}")
            logging.info(f"Action succeeded on attempt {attempt}")
            return result
        else:
            print(f"⚠️ Attempt {attempt} failed, retrying...")
            logging.warning(f"Attempt {attempt} failed for action: {action_plan_json}")
    print("❌ Action failed after max retries")
    logging.error(f"Action failed after {max_retries} retries: {action_plan_json}")
    return {"status": "failed"}
