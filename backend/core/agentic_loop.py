# backend/core/agentic_loop.py
from backend.core.perceive import perceive
from backend.core.plan import plan
from backend.core.act import act_with_retry
import logging

def run_cycle():
    perception = perceive()
    action_plan = plan(perception)
    action_result = act_with_retry(action_plan, max_retries=3)

    evaluation = {
        "success": action_result.get("status") == "success"
    }

    logging.info(f"📊 Evaluation result: {evaluation}")

    return {
        "perception": perception,
        "action_plan": action_plan,
        "action_result": action_result,
        "evaluation": evaluation
    }
