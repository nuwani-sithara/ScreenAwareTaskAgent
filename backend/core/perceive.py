import requests
import logging

VISION_BASE_URL = "http://localhost:8001"  # Vision FastAPI service

def perceive():
    """
    Agent perception step.
    Requests screen data from the Vision component.
    """
    logging.info("👁️ Requesting perception data from Vision service...")

    try:
        response = requests.post(f"{VISION_BASE_URL}/vision/capture", timeout=5)
        response.raise_for_status()

        perception_data = response.json()

        logging.info("📄 Perception data received successfully")
        return perception_data

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Vision service error: {e}")
        return {
            "error": "vision_unavailable",
            "screen_text": "",
            "detections": []
        }
