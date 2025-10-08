from fastapi import FastAPI
from backend.core.agentic_loop import run_cycle

app = FastAPI(title="ScreenPilot Backend", version="0.1")
@app.get("/")
def read_root():
    return {"message": "ScreenPilot backend is running 🚀"}

@app.get("/mock-loop")
def mock_loop():
    """Simulate Perceive → Plan → Act loop"""
    result = run_cycle()
    return {"result": result}
