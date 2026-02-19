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


# backend/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

from backend.core.agentic_loop import run_cycle, execute_steps

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


# 🔥 Main Agentic Loop Endpoint
@app.post("/run-cycle")
def run_agentic_cycle(request: TaskRequest):
    logging.info(f"📝 Received Task From Frontend: {request.task}")

    result = run_cycle(user_task=request.task)

    return result


# ------------------------------------
# Optional LLM Steps Receiver & Executor
# ------------------------------------
@app.post("/llm/steps")
async def receive_llm_steps(request: Request):
    """Receive LLM-generated steps and execute them via agentic loop."""
    try:
        payload = await request.json()
        logging.info(f"📥 Received LLM steps payload: {payload}")

        instruction = payload.get("instruction", "")
        steps = payload.get("steps", [])
        
        if not instruction:
            return {"status": "error", "detail": "No instruction provided"}
        
        # Decide execution mode
        if steps and len(steps) > 0:
            # Mode 1: Execute provided steps (step-by-step execution)
            logging.info(f"🎯 Mode: Executing {len(steps)} predefined steps")
            execution_result = execute_steps(steps, instruction, use_vision=True)
        else:
            # Mode 2: No steps provided, use autonomous agentic loop
            logging.warning("⚠️ No steps provided, using autonomous agentic loop")
            logging.info(f"🚀 Executing task via autonomous agentic loop: {instruction}")
            execution_result = run_cycle(user_task=instruction)
        
        logging.info(f"✅ Execution completed. Success: {execution_result.get('evaluation', {}).get('success', False)}")
        
        return {
            "status": "executed",
            "instruction": instruction,
            "steps_count": len(steps),
            "execution_result": execution_result
        }

    except Exception as e:
        logging.exception("❌ Failed to execute LLM steps")
        return {"status": "error", "detail": str(e)}