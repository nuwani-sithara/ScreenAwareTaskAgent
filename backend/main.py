from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Request
import logging
from backend.core.agentic_loop import run_cycle

# 1️⃣ Create FastAPI instance
app = FastAPI(title="ScreenPilot Backend", version="0.1")

# 2️⃣ Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3️⃣ Define routes
@app.get("/")
def read_root():
    return {"message": "ScreenPilot backend is running 🚀"}

@app.get("/mock-loop")
def mock_loop():
    return run_cycle()


# 4️⃣ LLM Steps Receiver Endpoint
@app.post("/llm/steps")
async def receive_llm_steps(request: Request):
    """Receive LLM-generated steps as JSON and process them."""
    try:
        steps = await request.json()
        logging.info(f"Received LLM steps: {steps}")
        # TODO: Add further processing of steps if needed
        return {"status": "received", "steps": steps}
    except Exception as e:
        logging.error(f"Failed to process LLM steps: {e}")
        return {"status": "error", "detail": str(e)}

