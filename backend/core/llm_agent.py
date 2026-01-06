import logging
from dotenv import load_dotenv

# Attempt to import LangChain LLMs; fall back to a simple mock if unavailable
try:
    from langchain_core.prompts import PromptTemplate
    from langchain_community.llms import Ollama
    LLM_AVAILABLE = True
except Exception as e:
    logging.warning(f"LLM libraries not installed or failed to import: {e}")
    LLM_AVAILABLE = False

load_dotenv()

# --- Logging Setup ---
logging.basicConfig(
    filename="agentic_ai_log.txt",  # Log file
    level=logging.INFO,             # Log level
    format="%(asctime)s - %(levelname)s - %(message)s",
)

if LLM_AVAILABLE:
    llm = Ollama(model="llama3.1")

    template = """
You are an intelligent Agentic AI responsible for planning UI actions.
Given this screen observation: {screen_info}
Plan the next action in one short sentence.
"""

    prompt = PromptTemplate(
        template=template,
        input_variables=["screen_info"]
    )

    chain = prompt | llm

    def generate_plan(screen_info: str):
        result = chain.invoke({"screen_info": screen_info})
        return result
else:
    # Lightweight fallback: return a simple, deterministic plan based on observed text
    def generate_plan(screen_info: str):
        logging.warning("Using mock generate_plan because LLM libs are not installed.")
        # Use the first non-empty line as a hint for a click target
        lines = [ln.strip() for ln in screen_info.splitlines() if ln.strip()]
        target = lines[0][:80] if lines else "screen"
        return f"click on {target}"
