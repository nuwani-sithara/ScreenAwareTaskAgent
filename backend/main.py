
# backend/main.py

import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging

from backend.core.agentic_loop import run_cycle
from backend.core.agentic_loop_v2 import run_agentic_loop_v2
from llm.interactive_generate import run_interactive
from backend.core.chat_controller import handle_chat

# ------------------------------------
# Logging Setup
# ------------------------------------
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# ------------------------------------
# FastAPI App
# ------------------------------------
app = FastAPI(title="ScreenPilot Backend", version="0.1")

# ------------------------------------
# Auto-start HID server if not running
# ------------------------------------
HID_SERVER_DIR = Path(__file__).resolve().parent.parent / "hid" / "api-server"
HID_HEALTH_URL = "http://localhost:3015/health"

def _ensure_hid_server() -> None:
    """Start the HID API server if it is not already reachable."""
    import urllib.request
    try:
        urllib.request.urlopen(HID_HEALTH_URL, timeout=2)
        logger.info("HID API server already running on port 3015.")
        return
    except Exception:
        pass  # not running — start it

    server_js = HID_SERVER_DIR / "dist" / "server.js"
    if not server_js.exists():
        logger.warning("HID server dist not found at %s — skipping auto-start.", server_js)
        return

    try:
        if sys.platform == "win32":
            # Detached from parent so it survives backend restarts
            subprocess.Popen(
                ["node", "dist/server.js"],
                cwd=str(HID_SERVER_DIR),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["node", "dist/server.js"],
                cwd=str(HID_SERVER_DIR),
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        logger.info("HID API server launched (port 3015).")
    except Exception as exc:
        logger.warning("Could not auto-start HID server: %s", exc)

_ensure_hid_server()

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


# In-memory store for active V2 runs (keyed by run_id).
# NOTE: This is single-process only. Use Redis or similar for multi-worker deployments.
_pending_runs: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "ScreenPilot backend is running 🚀"}


# 🔥 Main Agentic Loop Endpoint
@app.post("/run-cycle")
def run_agentic_cycle(request: TaskRequest):
    logging.info(f"📝 Received Task From Frontend: {request.task}")

    result = run_cycle(user_task=request.task)

    return result


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ProvideInputRequest(BaseModel):
    value: str


@app.post("/chat")
def chat(request: ChatRequest):

    logging.info(f"💬 User Message: {request.message}")

    response = handle_chat(
        request.session_id,
        request.message
    )

    return response


# ---------------------------------------------------------------------------
# V2 Agentic Loop — SSE streaming endpoint
# ---------------------------------------------------------------------------

@app.post("/run-cycle-v2")
async def run_cycle_v2_endpoint(request: TaskRequest):
    """
    Start a V2 agentic run and stream real-time progress as Server-Sent Events.

    Each event is a JSON object on a ``data: {...}\\n\\n`` line.
    Event types: run_started | todo_created | step_start | step_executing |
                 step_done | step_error | step_permanently_failed | retrying |
                 needs_input | input_received | screen_captured | log |
                 final_report | fatal_error | error | done
    """
    run_id = str(uuid.uuid4())
    event_queue: asyncio.Queue = asyncio.Queue()
    input_event: asyncio.Event = asyncio.Event()
    input_data_store: Dict[str, Any] = {}

    _pending_runs[run_id] = {
        "event_queue": event_queue,
        "input_event": input_event,
        "input_data_store": input_data_store,
    }

    logging.info("🚀 V2 run started: %s  task=%s", run_id, request.task[:80])

    # Launch the agentic loop as a background coroutine
    asyncio.create_task(
        run_agentic_loop_v2(
            user_task=request.task,
            run_id=run_id,
            event_queue=event_queue,
            input_event=input_event,
            input_data_store=input_data_store,
        )
    )

    async def event_stream():
        # First packet carries the run_id so the client can route /provide-input
        yield f"data: {json.dumps({'type': 'run_started', 'run_id': run_id})}\n\n"

        try:
            while True:
                try:
                    event_json = await asyncio.wait_for(
                        event_queue.get(), timeout=360.0
                    )
                    yield f"data: {event_json}\n\n"

                    evt = json.loads(event_json)
                    if evt.get("type") in ("done", "error", "fatal_error"):
                        break

                except asyncio.TimeoutError:
                    yield (
                        f"data: {json.dumps({'type': 'error', 'message': 'Agent timed out'})}\n\n"
                    )
                    break
        finally:
            _pending_runs.pop(run_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # Disable nginx buffering for SSE
        },
    )


@app.post("/provide-input/{run_id}")
async def provide_input_endpoint(run_id: str, request: ProvideInputRequest):
    """
    Inject user-supplied data into a paused V2 run.

    The agentic loop suspends when it needs information only the user can
    provide (passwords, OTPs, personal details).  POST to this endpoint with
    the value to resume execution.
    """
    run = _pending_runs.get(run_id)
    if not run:
        return {"error": "Run not found or already completed", "run_id": run_id}

    run["input_data_store"]["value"] = request.value
    run["input_event"].set()

    logging.info("✅ Input provided for run %s", run_id)
    return {"status": "ok", "run_id": run_id}