# 🏗️ Microservices Architecture Overview

## Three Independent API Services

Your ScreenPilot system now consists of **three microservices** that work together:

---

## 📊 Service Comparison

| **Aspect**        | **Vision Service** | **LLM Service** | **HID Service** |
|-------------------|-------------------|-----------------|----------------|
| **Port**          | 8001              | 8002            | 3015           |
| **Language**      | Python (FastAPI)  | Python (FastAPI)| TypeScript (Express) |
| **Purpose**       | Screen perception | Step generation | HID control    |
| **Main File**     | `vision/src/api.py` | `llm/api.py`  | `hid/api-server/src/server.ts` |
| **Dependencies**  | OpenCV, YOLOv8, OCR | Ollama, Mistral | SerialPort, ESP32 |
| **Communication** | REST + SSE        | REST            | REST           |

---

## 🎨 Architecture Diagram

```
                    ┌─────────────────────────┐
                    │  Frontend (React)       │
                    │  Port: 5173            │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  Backend (FastAPI)      │
                    │  Port: 8000            │
                    │  • Orchestrator         │
                    │  • Agentic Loop         │
                    └─┬──────────┬──────────┬─┘
                      │          │          │
        ┌─────────────▼┐    ┌───▼────┐  ┌─▼──────────┐
        │ Vision API   │    │ LLM    │  │ HID API    │
        │ Port: 8001   │    │ API    │  │ Port: 3015 │
        │              │    │ 8002   │  │            │
        │ • Capture    │    │        │  │ • Commands │
        │ • YOLOv8     │    │ • Gen  │  │ • Motion   │
        │ • OCR        │    │ • Val  │  │ • Queue    │
        │ • Elements   │    │ • Rew  │  │ • ACK      │
        └──────┬───────┘    └───┬────┘  └─────┬──────┘
               │                │              │
        ┌──────▼─────┐   ┌─────▼─────┐   ┌────▼────┐
        │ Camera/    │   │  Ollama   │   │ ESP32   │
        │ Webcam     │   │  Mistral  │   │ HID USB │
        └────────────┘   └───────────┘   └─────────┘
```

---

## 🚀 Starting All Services

### Complete Startup Sequence

```powershell
# Terminal 1: Backend (Orchestrator)
cd D:\SLIIT\Y4S1\RP\Project_works\ScreenAwareTaskAgent
.\venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Vision Service
cd vision
python src/api.py
# Or: python -m uvicorn src.api:app --reload --port 8001

# Terminal 3: LLM Service
cd llm
.\start_llm_service.ps1
# Or: python -m uvicorn llm.api:app --reload --port 8002

# Terminal 4: HID Service (if available)
cd hid/api-server
npm start

# Terminal 5: Frontend
cd frontend
npm run dev
```

---

## 📡 API Endpoints Reference

### 🎥 Vision Service (8001)

```http
POST   /vision/start       # Start capture session
POST   /vision/stop        # Stop and process
POST   /vision/capture     # Single snapshot
GET    /vision/stream      # SSE real-time stream
GET    /vision/status      # Service status
```

**Example Request:**
```bash
curl -X POST http://localhost:8001/vision/start
```

---

### 🧠 LLM Service (8002)

```http
POST   /llm/generate       # Full pipeline (validation + rewriting)
POST   /llm/simple         # Simple generation
GET    /llm/health         # Health check + Ollama status
GET    /llm/status         # Service info
GET    /                   # API docs
```

**Example Request:**
```bash
curl -X POST http://localhost:8002/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Open Chrome browser"}'
```

---

### 🖱️ HID Service (3015)

```http
POST   /hid/command        # Execute HID command
GET    /hid/status         # Device status
GET    /health             # Health check
GET    /                   # API docs
```

**Example Request:**
```bash
curl -X POST http://localhost:3015/hid/command \
  -H "Content-Type: application/json" \
  -d '{
    "type": "mouse_move",
    "payload": {"dx": 100, "dy": 50, "smooth": true}
  }'
```

---

## 🔄 Request Flow Example

### User Task: "Click the login button"

```
1. User Input (Frontend)
   ↓ POST /llm/steps (Backend 8000)
   
2. Backend calls LLM Service
   ↓ POST http://localhost:8002/llm/generate
   ↓ {"instruction": "Click the login button"}
   
3. LLM Service returns:
   ✓ Generated steps with validation
   
4. Backend decides: "Need vision for this"
   ↓ POST http://localhost:8001/vision/start
   ↓ GET http://localhost:8001/vision/capture
   
5. Vision Service returns:
   ✓ Screen text, UI elements, bounding boxes
   
6. Backend plans action based on perception
   
7. Backend executes via HID
   ↓ POST http://localhost:3015/hid/command
   ↓ {"type": "mouse_click", "payload": {...}}
   
8. HID Service returns:
   ✓ Command executed successfully
   
9. Backend evaluates result
   ↓ POST http://localhost:8001/vision/stop
   
10. Return result to Frontend
```

---

## 🧪 Testing Each Service

### Vision Service
```bash
cd vision
python src/api.py
# Test: curl http://localhost:8001/vision/status
```

### LLM Service
```bash
cd llm
python test_llm_service.py
```

### HID Service
```bash
cd hid/api-server
npm start
# Test: curl http://localhost:3015/health
```

---

## 📦 Service Dependencies

### Vision Service
```txt
fastapi
uvicorn
opencv-python
ultralytics  # YOLOv8
easyocr
pytesseract
numpy
pillow
```

### LLM Service
```txt
fastapi
uvicorn
pydantic
ollama (external)
transformers
torch
```

### HID Service
```txt
express
cors
serialport
typescript
```

---

## ✅ Health Checks

Quick check if all services are running:

```powershell
# Check all services
curl http://localhost:8000/        # Backend
curl http://localhost:8001/vision/status  # Vision
curl http://localhost:8002/llm/health     # LLM
curl http://localhost:3015/health         # HID
curl http://localhost:5173/               # Frontend
```

---

## 🛠️ Development Tips

### 1. Independent Development
Each service can be developed independently:
- Work on vision without touching LLM
- Update HID without affecting perception
- Modify backend orchestration separately

### 2. Easy Testing
Test each service in isolation:
```bash
# Test LLM independently
curl -X POST http://localhost:8002/llm/simple \
  -d '{"prompt": "Test"}'
```

### 3. Horizontal Scaling
Run multiple instances:
```bash
# Multiple LLM workers
python -m uvicorn llm.api:app --port 8002
python -m uvicorn llm.api:app --port 8003
python -m uvicorn llm.api:app --port 8004
```

### 4. Error Isolation
If LLM service crashes, Vision and HID still work.

---

## 🔒 Security Considerations

### Current Setup (Development)
- All services on localhost
- CORS enabled for `*` (all origins)
- No authentication

### Production Recommendations
- Use API keys for authentication
- Restrict CORS to specific origins
- Use HTTPS with SSL certificates
- Implement rate limiting
- Add request validation
- Use environment variables for sensitive config

---

## 📈 Performance Metrics

| Service | Typical Response Time | Resource Usage |
|---------|----------------------|----------------|
| Vision  | 2-5s (with detection) | High GPU/CPU |
| LLM     | 2-5s (generation)     | High GPU/RAM |
| HID     | <100ms (commands)     | Low |
| Backend | Variable (orchestrates) | Medium |

---

## 🐛 Common Issues & Solutions

### Port Already in Use
```powershell
# Find process using port
netstat -ano | findstr :8002

# Kill process (Windows)
taskkill /PID <PID> /F
```

### Service Won't Start
```bash
# Check Python/Node version
python --version  # Should be 3.8+
node --version    # Should be 14+

# Reinstall dependencies
pip install -r requirements.txt
npm install
```

### Ollama Not Available
```bash
# Start Ollama
ollama serve

# Pull Mistral model
ollama pull mistral
```

---

## 📚 Documentation Links

- [Main README](../README.md)
- [Vision Service](../vision/README.md)
- [LLM Service](LLM_SERVICE_README.md)
- [HID Service](../hid/README.md)
- [Backend Integration](../LLM_AGENTIC_INTEGRATION_FIXED.md)

---

## 🎯 Next Steps

1. **Start all services** using the commands above
2. **Test each service** individually
3. **Run full integration test** through frontend
4. **Monitor logs** for any errors
5. **Optimize performance** based on your use case

---

**All three microservices are now operational! 🚀**
