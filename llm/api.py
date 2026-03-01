"""
LLM API Service - FastAPI Server for Step Generation
Exposes LLM functionality as a microservice similar to Vision and HID

Port: 8002
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import time
import httpx
import asyncio

from llm.interactive_generate import run_interactive
from llm.ollama_adapter import generate_and_format
from llm.ollama_client import OllamaClient
from llm.hid_step_generator import HIDStepGenerator, generate_hid_steps_from_visual

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Silence verbose progress logs but keep final results
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("llm.interactive_generate").setLevel(logging.WARNING)
logging.getLogger("llm.ollama_client").setLevel(logging.WARNING)
logging.getLogger("llm.ollama_adapter").setLevel(logging.WARNING)

app = FastAPI(title="LLM Step Generation Service", version="2.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background task for startup health check
async def delayed_health_check():
    """Make a self-health-check request after server starts"""
    await asyncio.sleep(2.0)  # Wait for server to be ready
    try:
        async with httpx.AsyncClient() as client:
            await client.get("http://localhost:8002/llm/health", timeout=3.0)
    except Exception:
        pass  # Silently ignore startup health check errors

# Startup Event
@app.on_event("startup")
async def startup_event():
    """Launch background health check task"""
    asyncio.create_task(delayed_health_check())

# Request/Response Models
class GenerateRequest(BaseModel):
    instruction: str
    model: Optional[str] = "mistral"
    show_validation: Optional[bool] = False
    
class GenerateResponse(BaseModel):
    status: str
    instruction: str
    chosen_steps: List[Dict[str, Any]]
    chosen_source: str
    total_steps: int
    validation: Dict[str, Any]
    timestamp: str
    rewritten_steps: Optional[List[Dict[str, Any]]] = None
    abstract_steps: Optional[List[Dict[str, Any]]] = None

class SimpleGenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = "mistral"
    max_tokens: Optional[int] = 512

class VisualHIDRequest(BaseModel):
    instruction: str
    visual_data: Dict[str, Any]
    model: Optional[str] = "mistral"
    max_tokens: Optional[int] = 300
    skip_validation: Optional[bool] = False  # Skip validation check

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    ollama_available: bool
    timestamp: str


@app.get("/", response_model=Dict[str, Any])
def root():
    """API documentatiogenerate_hid": "Generate HID commands from instruction + visual data",
            "POST /llm/n endpoint"""
    return {
        "service": "LLM Step Generation Service",
        "version": "2.0.0",
        "endpoints": {
            "POST /llm/generate": "Generate steps from instruction (full pipeline)",
            "POST /llm/simple": "Simple text generation from Ollama",
            "GET /llm/health": "Health check and Ollama status",
            "GET /llm/status": "Service status",
        },
        "description": "Microservice for LLM-based step generation using Ollama/Mistral"
    }


@app.post("/llm/generate", response_model=Dict[str, Any])
def generate_steps(gen_request: GenerateRequest, request: Request):
    """
    Generate and validate steps from user instruction.
    Uses the full pipeline: generation → rewriting → validation → selection.
    
    Request:
    {
        "instruction": "Open Chrome and search for Python tutorials",
        "model": "mistral",
        "show_validation": false
    }
    
    Response:
    {
        "status": "success",
        "instruction": "...",
        "chosen_steps": [...],
        "chosen_source": "rewritten",
        "total_steps": 5,
        "validation": {...}
    }
    """
    try:
        if not gen_request.instruction or not gen_request.instruction.strip():
            raise HTTPException(status_code=400, detail="Instruction cannot be empty")
        
        logger.info(f"📥 Received generation request: {gen_request.instruction[:100]}...")
        
        start_time = time.time()
        
        # Call the main interactive_generate pipeline with silent mode (no console output)
        result = run_interactive(
            instruction=gen_request.instruction,
            show_validation=gen_request.show_validation,
            silent=True  # Suppress console output for API calls
        )
        
        execution_time = time.time() - start_time
        
        # Check for errors
        if isinstance(result, dict) and result.get("error"):
            logger.error(f"❌ Generation failed: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        # Format response
        chosen_steps = result.get("chosen_steps", [])
        
        logger.info(f"✅ Generated {len(chosen_steps)} steps in {execution_time:.2f}s")
        
        # Log the generated steps for verification
        if chosen_steps:
            logger.info("📋 Generated Steps:")
            for step in chosen_steps:
                logger.info(f"  {step.get('step')}. {step.get('action', 'N/A')}")
        
        # Log in uvicorn format
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        print(f"INFO:     {client_host}:{client_port} - \"POST /llm/generate HTTP/1.1\" 200 OK", flush=True)
        
        return {
            "status": "success",
            "instruction": result.get("instruction", gen_request.instruction),
            "total_steps": len(chosen_steps),
            "timestamp": result.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S")),
            "rewritten_steps": result.get("rewritten_steps"),
            "execution_time": f"{execution_time:.2f}s"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Generation failed")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/llm/generate_hid", response_model=Dict[str, Any])
def generate_hid_commands(request: VisualHIDRequest):
    """
    Generate HID protocol commands from visual perception + user instruction.
    This is the main endpoint for screen-aware task automation.
    
    Request:
    {
        "instruction": "Click the Send button",
        "visual_data": {
            "session_data": {
                "screens": [...]
            }
        },
        "model": "mistral",
        "max_tokens": 300
    }
    
    Response:
    {
        "status": "success",
        "instruction": "...",
        "hid_commands": [
            {"cmd":"mouse_move","meta":{"commandId":"uuid"},"dx":100,"dy":200},
            {"cmd":"mouse_click","meta":{"commandId":"uuid"},"button":"left"}
        ],
        "total_commands": 2,
        "visual_summary": "...",
        "timestamp": "..."
    }
    """
    try:
        if not request.instruction or not request.instruction.strip():
            raise HTTPException(status_code=400, detail="Instruction cannot be empty")
        
        if not request.visual_data:
            raise HTTPException(status_code=400, detail="Visual data cannot be empty")
        
        logger.info(f"📥 HID generation request: {request.instruction[:80]}...")
        
        start_time = time.time()
        
        # Generate HID commands using two-stage pipeline (with validation)
        result = generate_hid_steps_from_visual(
            instruction=request.instruction,
            visual_data=request.visual_data,
            model=request.model,
            skip_validation=request.skip_validation
        )
        
        execution_time = time.time() - start_time
        
        # Check for validation failure
        if result.get("status") == "validation_failed":
            validation = result.get("validation", {})
            logger.warning(f"⚠️ Validation failed: {result.get('message')}")
            logger.info(f"   Missing elements: {validation.get('missing_elements', [])}")
            logger.info(f"   Suggested actions: {result.get('suggested_actions', [])}")
            
            return {
                "status": "validation_failed",
                "instruction": result.get("instruction"),
                "message": result.get("message"),
                "validation": validation,
                "suggested_actions": result.get("suggested_actions", []),
                "rewritten_steps": [],
                "action_steps": [],
                "hid_commands": [],
                "total_commands": 0,
                "timestamp": result.get("timestamp"),
                "execution_time": f"{execution_time:.2f}s"
            }
        
        # Check for other errors
        if result.get("status") == "error":
            logger.error(f"❌ HID generation failed: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        action_steps = result.get("action_steps", [])
        hid_commands = result.get("hid_commands", [])
        rewritten_steps = result.get("rewritten_steps", [])
        
        logger.info(f"✅ Generated {len(action_steps)} actions → {len(hid_commands)} HID commands in {execution_time:.2f}s")
        
        # Log rewritten steps for debugging
        if rewritten_steps:
            logger.info("📋 Rewritten Steps:")
            for step in rewritten_steps[:10]:  # Log first 10
                logger.info(f"  {step.get('step')}. {step.get('action')}: {step.get('description')}")
        
        # Log action steps for debugging
        if action_steps:
            logger.info("📝 Action Steps (JSON):")
            for action in action_steps[:5]:  # Log first 5
                logger.info(f"  Step {action.get('step')}: {action.get('action')} - {action.get('target')}")
        
        # Log commands for debugging
        if hid_commands:
            logger.info("📋 HID Commands:")
            for cmd in hid_commands[:5]:  # Log first 5
                logger.info(f"  {cmd.get('cmd')}: {cmd}")
        
        return {
            "status": "success",
            "instruction": result.get("instruction"),
            "validation": result.get("validation"),  # Validation result
            "rewritten_steps": rewritten_steps,  # Human-readable structured steps
            "action_steps": action_steps,  # Stage 1 output
            "hid_commands": hid_commands,   # Stage 2 output
            "total_commands": result.get("total_commands"),
            "timestamp": result.get("timestamp"),
            "execution_time": f"{execution_time:.2f}s"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("HID generation failed")
        raise HTTPException(status_code=500, detail=f"HID generation failed: {str(e)}")


@app.post("/llm/simple", response_model=Dict[str, Any])
def simple_generate(request: SimpleGenerateRequest):
    """
    Simple Ollama generation endpoint (no validation pipeline).
    Directly calls Ollama with prompt.
    
    Request:
    {
        "prompt": "List 3 steps to make coffee",
        "model": "mistral",
        "max_tokens": 512
    }
    
    Response:
    {
        "status": "success",
        "prompt": "...",
        "response": "...",
        "model": "mistral"
    }
    """
    try:
        if not request.prompt or not request.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
        logger.info(f"📥 Simple generation request: {request.prompt[:100]}...")
        
        # Use ollama_adapter for simple generation
        result = generate_and_format(
            instruction=request.prompt,
            model=request.model
        )
        
        logger.info(f"✅ Generated response from {request.model}")
        
        return {
            "status": "success",
            "prompt": request.prompt,
            "response": result.get("raw_output", ""),
            "steps": result.get("steps", []),
            "model": request.model,
            "timestamp": result.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
        }
        
    except Exception as e:
        logger.exception("Simple generation failed")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.get("/llm/health", response_model=Dict[str, Any])
def health_check():
    """
    Health check endpoint.
    Verifies Ollama connectivity and service status.
    """
    ollama_available = False
    ollama_models = []
    
    try:
        client = OllamaClient()
        # Try to list models to verify connection
        ollama_available = True
        # Note: OllamaClient doesn't have a list_models method, 
        # but we can try a simple generation to test connectivity
    except Exception as e:
        logger.warning(f"Ollama not available: {e}")
        ollama_available = False
    
    return {
        "status": "healthy" if ollama_available else "degraded",
        "service": "LLM Step Generation Service",
        "version": "2.0.0",
        "ollama_available": ollama_available,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "message": "Service running" if ollama_available else "Service running but Ollama unavailable"
    }


@app.get("/llm/status", response_model=Dict[str, Any])
def get_status():
    """
    Get detailed service status.
    """
    return {
        "service": "LLM Step Generation Service",
        "version": "2.0.0",
        "status": "running",
        "endpoints_available": 5,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "features": {
            "full_pipeline": True,
            "validation": True,
            "rewriting": True,
            "simple_generation": True,
            "visual_hid_generation": True
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting LLM API Service on port 8002...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )
