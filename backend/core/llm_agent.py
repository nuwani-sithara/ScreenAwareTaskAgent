import logging
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_community.llms import Ollama

load_dotenv()

# --- Logging Setup ---
logging.basicConfig(
    filename="agentic_ai_log.txt",  # Log file
    level=logging.INFO,             # Log level
    format="%(asctime)s - %(levelname)s - %(message)s",
)

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
