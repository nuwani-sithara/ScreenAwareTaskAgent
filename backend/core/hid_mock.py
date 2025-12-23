# hid_mock.py
import logging

def send_hid_command(command_json: dict):
    """
    Mock function to simulate sending HID commands.
    Expects a JSON like: {"action": "click", "target": "username_field"}
    """
    logging.info(f"Mock HID received command: {command_json}")
    print(f"🖱️ [Dummy HID] Executing: {command_json}")
    # Simulate success
    return {"status": "success", "command_executed": command_json}
