import requests
import logging
import time

from backend.core.perceive import perceive, stream_vision
from backend.core.plan import plan
from backend.core.act import act_with_retry

VISION_BASE_URL = "http://localhost:8001"
LLM_BASE_URL = "http://localhost:8002"  # LLM FastAPI service

def start_vision():
    logging.info("Starting Vision capture loop...")
    requests.post(f"{VISION_BASE_URL}/vision/start")
 
def stop_vision():
    logging.info("Stopping Vision capture loop...")
    requests.post(f"{VISION_BASE_URL}/vision/stop")
 
def run_cycle(start_delay: float = 4.0, stop_at_end: bool = True):
    # 1️⃣ Ensure vision is running (after a short delay)
    if start_delay and start_delay > 0:
        time.sleep(start_delay)
    start_vision()
 
    # 2️⃣ Perceive
    perception = perceive()
 
    # 3️⃣ Plan
    action_plan = plan(perception)
 
    # 4️⃣ Act
    action_result = act_with_retry(action_plan, max_retries=3)
 
    # 5️⃣ Evaluate
    evaluation = {
        "success": action_result.get("status") == "success"
    }
 
    logging.info(f"📊 Evaluation result: {evaluation}")
 
    # 6️⃣ Agent decides to stop vision (example condition)
    if action_plan.get("stop_vision", False):
        stop_vision()
 
    # Optionally ensure vision is stopped at the end of the cycle
    if stop_at_end and not action_plan.get("stop_vision", False):
        stop_vision()
 
    return {
        "perception": perception,
        "action_plan": action_plan,
        "action_result": action_result,
        "evaluation": evaluation
    }


def run_streaming_cycle(max_events: int = 10):
    """Start vision capture and process incoming per-frame perception results in a loop.

    For each received `vision_data`, run planning and acting immediately. Stops early if
    an action_plan contains `stop_vision`.
    """
    logging.info("Starting streaming cycle...")
    start_vision()

    results = []
    try:
        for item in stream_vision(max_events=max_events):
            if not isinstance(item, dict):
                continue
            if item.get("error"):
                logging.warning(f"Received stream error: {item}")
                continue
            vision_data = item.get("vision_data") or item
            action_plan = plan(vision_data)
            action_result = act_with_retry(action_plan, max_retries=3)

            results.append({
                "perception": vision_data,
                "action_plan": action_plan,
                "action_result": action_result
            })

            if action_plan.get("stop_vision", False):
                logging.info("Action requested to stop vision. Stopping.")
                stop_vision()
                break

    finally:
        # Ensure vision is stopped
        stop_vision()

    return results