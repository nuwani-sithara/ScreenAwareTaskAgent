import logging
import json
import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
import requests

load_dotenv()

# --- Logging Setup ---
logging.basicConfig(
    filename="agentic_ai_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

llm = OllamaLLM(model="mistral:latest")

# Ask the LLM to return a JSON object describing the plan.
template = """
You are an intelligent Agentic AI responsible for planning UI actions.
Given this screen observation: {screen_info}
Return a JSON object (only JSON) with the following fields:
  - action: short action name (e.g., "click", "type", "navigate")
  - target: target identifier or selector
  - params: object with any action parameters (can be empty)
Return a single JSON object and nothing else.
"""

prompt = PromptTemplate(
    template=template,
    input_variables=["screen_info"]
)

chain = prompt | llm

# Optional URL to forward LLM JSON output to (e.g., agentic endpoint)
AGENTIC_API_URL = os.getenv("AGENTIC_API_URL")


def _post_to_agentic(json_payload: dict):
    if not AGENTIC_API_URL:
        return None
    try:
        r = requests.post(AGENTIC_API_URL, json=json_payload, timeout=10)
        r.raise_for_status()
        logging.info("Posted plan to agentic API %s: %s", AGENTIC_API_URL, r.status_code)
        return r.json() if r.headers.get("content-type", "").startswith("application/json") else {"status_code": r.status_code}
    except Exception as e:
        logging.error("Failed to post plan to agentic API: %s", e)
        return None


def generate_plan(screen_info: str):
    # produce text output from chain (expected to be JSON string)
    result = chain.invoke({"screen_info": screen_info})
    text = result if isinstance(result, str) else str(result)

    try:
        plan_json = json.loads(text)
    except Exception:
        # If the LLM didn't return strict JSON, wrap the raw text
        logging.warning("LLM plan not JSON, returning raw text in 'raw' field")
        plan_json = {"raw": text}

    # Forward the JSON to configured agentic API if set
    if isinstance(plan_json, dict):
        _post_to_agentic(plan_json)

    return plan_json
