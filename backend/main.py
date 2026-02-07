from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.agentic_loop import run_cycle

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

