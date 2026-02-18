from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

from backend.core.agentic_loop import run_cycle

# ------------------------------------
# Logging Setup
# ------------------------------------
logging.basicConfig(level=logging.INFO)

# ------------------------------------
# FastAPI App
# ------------------------------------
app = FastAPI(title="ScreenPilot Backend", version="0.1")

# ------------------------------------
# CORS Middleware
# ------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------
# Request Model
# ------------------------------------
class TaskRequest(BaseModel):
    task: str


# ------------------------------------
# Routes
# ------------------------------------
@app.get("/")
def read_root():
    return {"message": "ScreenPilot backend is running 🚀"}


# Main Agentic Loop Endpoint
@app.post("/run-cycle")
def run_agentic_cycle(request: TaskRequest):
    logging.info(f"📝 Received Task From Frontend: {request.task}")

    result = run_cycle(user_task=request.task)

    return result


# ------------------------------------
# LLM Steps Receiver & Auto-Executor
# ------------------------------------
@app.post("/llm/steps")
async def receive_llm_steps(request: Request):
    """
    Receives LLM-generated steps and automatically executes them through the agentic loop.
    
    Payload format:
    {
        "instruction": "add product to the cart",
        "chosen": "rewritten",
        "steps": [
            {"step": 1, "action": "...", "description": "..."},
            {"step": 2, "action": "...", "description": "..."}
        ],
        "timestamp": 1234567890
    }
    """
    try:
        data = await request.json()
        instruction = data.get("instruction", "")
        steps = data.get("steps", [])
        
        logging.info(f"📨 Received LLM steps for: '{instruction}'")
        logging.info(f"   Steps count: {len(steps)}")
        
        # Log each step
        for i, step in enumerate(steps, 1):
            action = step.get("action", "N/A")
            logging.info(f"   {i}. {action}")
        
        # 🔥 AUTO-EXECUTE: Run the instruction through the agentic loop
        logging.info(f"🚀 Auto-executing through agentic loop...")
        result = run_cycle(user_task=instruction)
        
        logging.info(f"✅ Execution completed. Success: {result.get('evaluation', {}).get('success', False)}")
        
        return {
            "status": "executed",
            "instruction": instruction,
            "steps_count": len(steps),
            "execution_result": result
        }
        
    except Exception as e:
        logging.error(f"❌ Failed to process/execute LLM steps: {e}")
        return {"status": "error", "detail": str(e)}



# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from fastapi import Request
# import logging
# from backend.core.agentic_loop import run_cycle

# # 1️⃣ Create FastAPI instance
# app = FastAPI(title="ScreenPilot Backend", version="0.1")

# # 2️⃣ Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],   # allow all for dev
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # 3️⃣ Define routes
# @app.get("/")
# def read_root():
#     return {"message": "ScreenPilot backend is running 🚀"}

# @app.get("/mock-loop")
# def mock_loop():
#     return run_cycle()


# # 4️⃣ LLM Steps Receiver Endpoint
# @app.post("/llm/steps")
# async def receive_llm_steps(request: Request):
#     """Receive LLM-generated steps as JSON and process them."""
#     try:
#         steps = await request.json()
#         logging.info(f"Received LLM steps: {steps}")
#         # TODO: Add further processing of steps if needed
#         return {"status": "received", "steps": steps}
#     except Exception as e:
#         logging.error(f"Failed to process LLM steps: {e}")
#         return {"status": "error", "detail": str(e)}