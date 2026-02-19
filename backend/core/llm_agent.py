# import logging
# import json
# import os
# from dotenv import load_dotenv
# from langchain_core.prompts import PromptTemplate
# from langchain_ollama import OllamaLLM
# import requests

# load_dotenv()

# # --- Logging Setup ---
# logging.basicConfig(
#     filename="agentic_ai_log.txt",
#     level=logging.INFO,
#     format="%(asctime)s - %(levelname)s - %(message)s",
# )

# llm = OllamaLLM(model="mistral:latest")

# # Ask the LLM to return a JSON object describing the plan.
# template = """
# You are an intelligent Agentic AI responsible for planning UI actions.
# Given this screen observation: {screen_info}
# Return a JSON object (only JSON) with the following fields:
#   - action: short action name (e.g., "click", "type", "navigate")
#   - target: target identifier or selector
#   - params: object with any action parameters (can be empty)
# Return a single JSON object and nothing else.
# """

# prompt = PromptTemplate(
#     template=template,
#     input_variables=["screen_info"]
# )

# chain = prompt | llm

# # Optional URL to forward LLM JSON output to (e.g., agentic endpoint)
# AGENTIC_API_URL = os.getenv("AGENTIC_API_URL")


# def _post_to_agentic(json_payload: dict):
#     if not AGENTIC_API_URL:
#         return None
#     try:
#         r = requests.post(AGENTIC_API_URL, json=json_payload, timeout=10)
#         r.raise_for_status()
#         logging.info("Posted plan to agentic API %s: %s", AGENTIC_API_URL, r.status_code)
#         return r.json() if r.headers.get("content-type", "").startswith("application/json") else {"status_code": r.status_code}
#     except Exception as e:
#         logging.error("Failed to post plan to agentic API: %s", e)
#         return None


# def generate_plan(screen_info: str):
#     # produce text output from chain (expected to be JSON string)
#     result = chain.invoke({"screen_info": screen_info})
#     text = result if isinstance(result, str) else str(result)

#     try:
#         plan_json = json.loads(text)
#     except Exception:
#         # If the LLM didn't return strict JSON, wrap the raw text
#         logging.warning("LLM plan not JSON, returning raw text in 'raw' field")
#         plan_json = {"raw": text}

#     # Forward the JSON to configured agentic API if set
#     if isinstance(plan_json, dict):
#         _post_to_agentic(plan_json)

#     return plan_json


import logging
import json
import os
import time
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
import requests

load_dotenv()

# --- Logging Setup ---
logging.basicConfig(
    filename="agentic_ai_log.txt",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

logger.info("=== Agentic AI System Started ===")

# --- LLM Setup ---
try:
    llm = OllamaLLM(model="mistral:latest")
    logger.info("LLM initialized successfully")
except Exception as e:
    logger.exception("LLM initialization failed")
    raise

# --- Prompt ---
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

AGENTIC_API_URL = os.getenv("AGENTIC_API_URL")


# --- API Forwarding ---
def _post_to_agentic(screen_info: str):

    AGENTIC_API_URL = "http://localhost:8000/llm/steps"

    if not AGENTIC_API_URL:
        logger.info("No agentic API URL configured — skipping post")
        return None

    logger.info("Posting plan to agentic API")

    try:
        response = requests.post(
            AGENTIC_API_URL,
            json={"instruction": screen_info},  # important fix
            timeout=120
        )

        logger.info("Status Code: %s", response.status_code)

        # 🔥 Get JSON body
        response_json = response.json()

        logger.info("Plan posted to agentic API response body: %s", response_json)

        return response_json

    except Exception:
        logger.exception("Failed posting to agentic API")
        return None


# --- Plan Generation ---
def generate_plan(screen_info: str):
    start_time = time.time()

    logger.info("Plan generation started")
    logger.info("Screen info received: %s", screen_info)

    # try:
    #     result = chain.invoke({"screen_info": screen_info})

    #     text = result if isinstance(result, str) else str(result)
    #     logger.info("Raw LLM output: %s", text)

    # except Exception:
    #     logger.exception("LLM invocation failed")
    #     return {"error": "LLM failure"}

    # # JSON parsing
    # try:
    #     plan_json = json.loads(text)
    #     logger.info("JSON parsing successful")

    # except Exception:
    #     logger.warning("LLM output not valid JSON — wrapping raw text")
    #     plan_json = {"raw": text}

    # API forwarding
    result= _post_to_agentic(screen_info)
    logger.info("Plan posted to agentic API: %s", result)

    elapsed = round(time.time() - start_time, 2)
    logger.info("Plan generation completed in %ss", elapsed)

    return result