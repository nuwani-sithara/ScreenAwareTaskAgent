import requests
import logging

from backend.core.perceive import perceive
from backend.core.plan import plan
from backend.core.act import act_with_retry

VISION_BASE_URL = "http://localhost:8001"
LLM_BASE_URL = "http://localhost:8002"  # LLM FastAPI service

def start_vision():
    logging.info("▶️ Starting Vision capture loop...")
    requests.post(f"{VISION_BASE_URL}/vision/start")

def stop_vision():
    logging.info("⏹️ Stopping Vision capture loop...")
    requests.post(f"{VISION_BASE_URL}/vision/stop")

def run_cycle():
    # 1️⃣ Ensure vision is running
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

    return {
        "perception": perception,
        "action_plan": action_plan,
        "action_result": action_result,
        "evaluation": evaluation
    }
