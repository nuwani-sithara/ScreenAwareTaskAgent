"""Compatibility shim for older callers.

The project now routes mouse and keyboard execution through ``hid/api-server``.
This adapter keeps older imports working by forwarding a single command through
the HID API server.
"""

from backend.core.act import HID_API_URL
import requests


def send_hid_command(command_json: dict):
    """Execute one command through the HID API server."""
    payload = {
        "type": command_json.get("cmd") or command_json.get("type"),
        "payload": {k: v for k, v in command_json.items() if k not in ["cmd", "type", "meta"]},
    }

    response = requests.post(HID_API_URL, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("success") or data.get("status") == "ok":
        return {"status": "success", "command_executed": command_json}

    return {
        "status": "failed",
        "command_executed": command_json,
        "reason": data.get("message") or data.get("error") or "automation_failed",
    }

