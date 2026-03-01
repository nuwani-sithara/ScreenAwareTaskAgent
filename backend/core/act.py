import requests
import logging
import time

HID_API_URL = "http://localhost:3015/hid/command"

def act_with_retry(action_plan_json: dict, max_retries: int = 3):
    logging.info("🚀 Starting HID execution process...")

    hid_commands = action_plan_json.get("hid_commands", [])

    if not hid_commands:
        logging.warning("⚠️ No HID commands found.")
        return {"status": "no_commands"}

    for index, command in enumerate(hid_commands):
        cmd_type = command.get("cmd")

        # Prepare payload for HID API
        payload = {
            "type": cmd_type,
            "payload": {
                k: v for k, v in command.items()
                if k not in ["cmd", "meta"]
            }
        }

        attempt = 0
        success = False

        while attempt < max_retries and not success:
            try:
                logging.info(f"🖱️ Executing command {index + 1}/{len(hid_commands)}: {cmd_type}")
                logging.debug(f"Payload: {payload}")

                response = requests.post(HID_API_URL, json=payload, timeout=30)
                response.raise_for_status()

                result = response.json()
                logging.info(f"✅ HID response: {result}")

                if result.get("success") or result.get("status") == "ok":
                    success = True
                else:
                    raise Exception("Device returned non-success response")

            except Exception as e:
                attempt += 1
                logging.warning(f"⚠️ Command failed (Attempt {attempt}/{max_retries}): {e}")
                time.sleep(1)

        if not success:
            logging.error(f"❌ Failed command after {max_retries} retries.")
            return {
                "status": "failed",
                "failed_command": command
            }

        # Small delay between commands to mimic human pacing
        time.sleep(0.2)

    logging.info("🎉 All HID commands executed successfully.")

    return {
        "status": "success",
        "total_executed": len(hid_commands)
    }