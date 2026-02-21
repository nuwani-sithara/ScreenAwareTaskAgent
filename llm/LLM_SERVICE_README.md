# LLM API Service

**Microservice for AI-powered step generation using Ollama/Mistral**

Similar to Vision (port 8001) and HID (port 3015), the LLM module now runs as an independent API service.

---

## 🚀 Quick Start

### Start the Service

**Windows PowerShell:**
```powershell
cd llm
.\start_llm_service.ps1
```

**Linux/Mac:**
```bash
cd llm
chmod +x start_llm_service.sh
./start_llm_service.sh
```

**Manual Start:**
```bash
# From project root
python -m uvicorn llm.api:app --reload --port 8002
```

---

## 📡 API Endpoints

### Base URL
```
http://localhost:8002
```

### 1. **POST /llm/generate** - Full Pipeline Generation

Generate steps with validation, rewriting, and quality scoring.

**Request:**
```json
{
  "instruction": "Open Chrome and search for Python tutorials",
  "model": "mistral",
  "show_validation": false
}
```

**Response:**
```json
{
  "status": "success",
  "instruction": "Open Chrome and search for Python tutorials",
  "chosen_steps": [
    {
      "step": 1,
      "action": "Open Chrome browser",
      "description": "Launch the Chrome application"
    },
    {
      "step": 2,
      "action": "Click address bar",
      "description": "Focus the browser address bar"
    },
    {
      "step": 3,
      "action": "Type search query",
      "description": "Enter 'Python tutorials' in the search bar"
    }
  ],
  "chosen_source": "rewritten",
  "total_steps": 3,
  "validation": {
    "original_quality": {...},
    "rewritten_quality": {...}
  },
  "timestamp": "2026-02-20T10:30:45",
  "execution_time": "2.34s"
}
```

---

### 2. **POST /llm/simple** - Basic Text Generation

Direct Ollama generation without validation pipeline.

**Request:**
```json
{
  "prompt": "List 3 steps to make coffee",
  "model": "mistral",
  "max_tokens": 512
}
```

**Response:**
```json
{
  "status": "success",
  "prompt": "List 3 steps to make coffee",
  "response": "1. Boil water\n2. Add coffee grounds\n3. Pour and enjoy",
  "steps": [
    {"step": 1, "action": "Boil water"},
    {"step": 2, "action": "Add coffee grounds"},
    {"step": 3, "action": "Pour and enjoy"}
  ],
  "model": "mistral",
  "timestamp": "2026-02-20T10:30:45"
}
```

---

### 3. **GET /llm/health** - Health Check

Check service and Ollama connectivity.

**Response:**
```json
{
  "status": "healthy",
  "service": "LLM Step Generation Service",
  "version": "2.0.0",
  "ollama_available": true,
  "timestamp": "2026-02-20T10:30:45",
  "message": "Service running"
}
```

---

### 4. **GET /llm/status** - Service Status

Get detailed service information.

**Response:**
```json
{
  "service": "LLM Step Generation Service",
  "version": "2.0.0",
  "status": "running",
  "endpoints_available": 4,
  "timestamp": "2026-02-20T10:30:45",
  "features": {
    "full_pipeline": true,
    "validation": true,
    "rewriting": true,
    "simple_generation": true
  }
}
```

---

## 🔧 Integration with Backend

### Current Usage (Direct Import)
```python
# backend/main.py - OLD WAY
from llm.interactive_generate import run_interactive

result = run_interactive(instruction=instruction)
```

### New Usage (API Service)
```python
# backend/main.py - NEW WAY
import requests

LLM_BASE_URL = "http://localhost:8002"

response = requests.post(
    f"{LLM_BASE_URL}/llm/generate",
    json={
        "instruction": instruction,
        "model": "mistral",
        "show_validation": False
    },
    timeout=120
)

result = response.json()
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│           Backend (Port 8000)                   │
│         Main Orchestrator                       │
└────┬──────────────┬──────────────┬─────────────┘
     │              │              │
     ↓              ↓              ↓
┌─────────┐   ┌──────────┐   ┌──────────┐
│ Vision  │   │   LLM    │   │   HID    │
│  8001   │   │   8002   │   │   3015   │
└─────────┘   └──────────┘   └──────────┘
     │              │              │
     ↓              ↓              ↓
  Camera        Ollama         ESP32-S3
```

---

## ✅ Features

- **Full Pipeline**: Generation → Rewriting → Validation → Selection
- **Step Validation**: Quality scoring and algorithmic validation
- **Multiple Modes**: Full pipeline or simple generation
- **CORS Enabled**: Accessible from any origin
- **Health Monitoring**: Built-in health check endpoints
- **Fast**: Typical response time 2-5 seconds
- **Stateless**: Each request is independent

---

## 🔍 Testing the Service

### Using curl

**Generate Steps:**
```bash
curl -X POST http://localhost:8002/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Open calculator app"}'
```

**Health Check:**
```bash
curl http://localhost:8002/llm/health
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8002/llm/generate",
    json={"instruction": "Login to Gmail"}
)

data = response.json()
print(f"Generated {data['total_steps']} steps")
for step in data['chosen_steps']:
    print(f"  {step['step']}. {step['action']}")
```

---

## 📋 Requirements

- **Python 3.8+**
- **Ollama** running on `localhost:11434`
- **Mistral model** installed: `ollama pull mistral`
- Python packages:
  - `fastapi`
  - `uvicorn`
  - `pydantic`
  - All packages in `llm/requirements.txt`

---

## 🐛 Troubleshooting

### Service won't start
```bash
# Check if port 8002 is already in use
netstat -ano | findstr :8002

# Kill process if needed (Windows)
taskkill /PID <PID> /F
```

### Ollama not available
```bash
# Start Ollama service
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

### Import errors
```bash
# Install dependencies
pip install -r llm/requirements.txt
```

---

## 🔄 Migration Guide

To migrate from direct LLM imports to the API service:

1. **Start the LLM service** (port 8002)
2. **Update backend code** to use HTTP requests instead of direct imports
3. **Update error handling** to handle HTTP errors
4. **Test all endpoints** before deploying

Example migration in [backend/main.py](../backend/main.py):
- Replace `run_interactive()` calls with API requests
- Add timeout handling (recommended: 120s)
- Handle connection errors gracefully

---

## 📊 Benefits of Microservice Architecture

✅ **Independent Scaling** - Scale LLM service separately  
✅ **Language Flexibility** - Can rewrite in any language  
✅ **Fault Isolation** - LLM failures don't crash backend  
✅ **Easy Testing** - Test LLM service independently  
✅ **Deployment Flexibility** - Run on different machines  
✅ **Load Balancing** - Multiple LLM instances possible  

---

## 🚀 Running All Services

```powershell
# Terminal 1: Backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Vision Service
cd vision
python src/api.py

# Terminal 3: LLM Service
cd llm
python -m uvicorn api:app --reload --port 8002

# Terminal 4: HID Service (if available)
cd hid/api-server
npm start

# Terminal 5: Frontend
cd frontend
npm run dev
```

---

For more information, see:
- [Main README](../README.md)
- [LLM Integration Guide](../LLM_AGENTIC_INTEGRATION_FIXED.md)
- [Ollama Setup](README_OLLAMA.md)
