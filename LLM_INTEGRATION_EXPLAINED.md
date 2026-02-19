# 🔗 LLM → Agentic AI Integration: How It Works

## 📊 Current Architecture

Your system already has **automatic step transmission** from LLM to backend!

```
┌──────────────────────────────────────────────────────────────┐
│                    COMPLETE FLOW                             │
└──────────────────────────────────────────────────────────────┘

    User runs command
          ↓
    python -m llm.interactive_generate
          ↓
    Enter instruction: "add product to cart"
          ↓
┌─────────────────────────────────┐
│  LLM Module Processing          │
│  • Ollama generates steps       │
│  • Flan-T5 rewrites (optional)  │
│  • Validation & quality check   │
│  • Best steps selected          │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  Steps Saved Locally            │
│  ✅ llm/interactive_results.json│
│  ✅ llm/esp32_steps.jsonl       │
│  ✅ llm/esp32_display.jsonl     │
└────────────┬────────────────────┘
             ↓
    📡 HTTP POST (Automatic!)
             ↓
┌─────────────────────────────────┐
│  Backend receives steps         │
│  POST /llm/steps                │
│                                 │
│  Response: 200 OK               │
│  ✅ Steps received              │
│  ✅ Logged to console           │
│  ⚠️  NOT executed yet           │
└─────────────────────────────────┘
```

---

## 📁 Code Locations

### 1. LLM Module Sends Steps
**File:** `llm/interactive_generate.py` (lines 265-272)

```python
# Send steps to agentic AI backend (optional - backend must be running)
try:
    import requests
    resp = requests.post(
        "http://localhost:8000/llm/steps", 
        json=compact, 
        timeout=5
    )
    print(f"✅ Sent steps to agentic AI backend: {resp.status_code}")
except requests.exceptions.ConnectionError:
    print("⚠️  Backend not running at localhost:8000 - steps saved locally only")
except Exception as e:
    print(f"⚠️  Failed to send steps to backend: {type(e).__name__}")
```

**Payload Structure:**
```json
{
  "instruction": "add product to the cart",
  "chosen": "rewritten",
  "steps": [
    {
      "step": 1,
      "action": "Navigate to the product page",
      "description": "Step 1: Navigate to the product page"
    },
    {
      "step": 2,
      "action": "Find and click the 'Add to Cart' button",
      "description": "Step 2: Find and click the 'Add to Cart' button"
    }
  ],
  "timestamp": 1234567890.123
}
```

### 2. Backend Receives Steps
**File:** `backend/main.py` (lines 103+)

```python
@app.post("/llm/steps")
async def receive_llm_steps(request: Request):
    """
    Receive LLM-generated steps from interactive_generate.py
    """
    try:
        data = await request.json()
        logging.info(f"📨 Received LLM steps: {data.get('instruction', 'N/A')}")
        logging.info(f"   Steps count: {len(data.get('steps', []))}")
        
        steps = data.get("steps", [])
        for i, step in enumerate(steps, 1):
            logging.info(f"   {i}. {step.get('action', 'N/A')}")
        
        return {
            "status": "received",
            "instruction": data.get("instruction"),
            "steps_count": len(steps),
            "steps": steps
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
```

---

## 🚀 How to Use

### Option 1: Generate & Send (Current - Automatic)

```powershell
# 1. Start backend first
uvicorn backend.main:app --reload

# 2. Run LLM generator (in another terminal)
python -m llm.interactive_generate

# 3. Enter your task
> Enter instruction: add product to the cart

# OUTPUT:
# Generating with Ollama...
# Rewriting with Flan-T5...
# --- Chosen Steps (rewritten) ---
# 1. Navigate to the product page
# 2. Find and click the 'Add to Cart' button
# 3. Verify product added to cart
# Saved result to llm\interactive_results.json
# ✅ Sent steps to agentic AI backend: 200    # ← THIS LINE!
# Appended chosen steps to llm\esp32_steps.jsonl
```

**What Happens:**
- ✅ Steps generated
- ✅ Steps saved locally
- ✅ Steps sent to backend (HTTP 200)
- ✅ Backend logs them
- ⚠️  **NOT executed automatically**

---

### Option 2: Execute Steps Manually

After generating steps, execute them:

```python
import requests
import json

# Read last generated steps
with open("llm/esp32_steps.jsonl", 'r') as f:
    lines = f.readlines()
    last_plan = json.loads(lines[-1])

# Send for execution
response = requests.post(
    "http://localhost:8000/llm/execute",
    json=last_plan,
    timeout=120
)

result = response.json()
print(f"Status: {result['status']}")
print(f"Steps executed: {result['total_steps']}")
```

**Or use the test script:**
```powershell
python test_llm_flow.py
```

---

### Option 3: Execute Single Steps

Execute one action at a time through the agentic loop:

```python
import requests

# Execute single action
response = requests.post(
    "http://localhost:8000/run-cycle",
    json={"task": "Click the login button"}
)

result = response.json()
print(f"Success: {result['evaluation']['success']}")
```

---

## 🔍 API Endpoints

### 1. `/llm/steps` - Receive Steps (Auto-called)
**Method:** POST  
**Purpose:** Receive steps from LLM module  
**Called by:** `interactive_generate.py` automatically  
**Action:** Logs steps, returns acknowledgment

**Request:**
```json
{
  "instruction": "task description",
  "steps": [
    {"step": 1, "action": "...", "description": "..."},
    {"step": 2, "action": "...", "description": "..."}
  ]
}
```

**Response:**
```json
{
  "status": "received",
  "instruction": "task description",
  "steps_count": 2,
  "steps": [...]
}
```

---

### 2. `/llm/execute` - Execute Received Steps
**Method:** POST  
**Purpose:** Execute steps through agentic loop  
**Called by:** You manually or from script

**Request:**
```json
{
  "instruction": "task description",
  "steps": [...]
}
```

**Response:**
```json
{
  "status": "completed",
  "total_steps": 3,
  "results": [
    {
      "step": 1,
      "action": "...",
      "result": {
        "vision_used": true,
        "perception": {...},
        "action_plan": {...},
        "evaluation": {"success": true}
      }
    }
  ]
}
```

---

### 3. `/run-cycle` - Single Action Execution
**Method:** POST  
**Purpose:** Execute single action  
**Called by:** Frontend or direct API call

**Request:**
```json
{
  "task": "Click the submit button"
}
```

**Response:**
```json
{
  "vision_used": true,
  "perception": {...},
  "action_plan": {...},
  "action_result": {...},
  "evaluation": {"success": true}
}
```

---

## 📊 What Gets Logged

When you run `python -m llm.interactive_generate`:

**Console Output:**
```
Enter instruction: add product to the cart
Generating with Ollama (strict prompt)...
Rewriting with Flan-T5 (or fallback)...

--- Chosen Steps (rewritten) ---
1. Navigate to the product page
2. Find and click the 'Add to Cart' button
3. Verify that the product has been added to the cart

Saved result to llm\interactive_results.json
✅ Sent steps to agentic AI backend: 200       ← SENT!
Appended chosen steps to llm\esp32_steps.jsonl
Appended human_readable display to llm\esp32_display.jsonl
Updated selection report: llm\selection_report.json
```

**Backend Logs:**
```
INFO:     127.0.0.1:xxxxx - "POST /llm/steps HTTP/1.1" 200 OK
Received LLM steps: add product to the cart
   Steps count: 3
   1. Navigate to the product page
   2. Find and click the 'Add to Cart' button
   3. Verify that the product has been added to the cart
```

---

## 🛠️ Troubleshooting

### Issue: "Backend not running at localhost:8000"
```powershell
# Start backend
uvicorn backend.main:app --reload
```

### Issue: "ConnectionError"
- Check backend is running on port 8000
- Verify no firewall blocking
- Check URL in code: `http://localhost:8000/llm/steps`

### Issue: Steps received but not executing
**This is normal!** The current flow only sends/receives. To execute:
```powershell
python test_llm_flow.py
```

---

## ✨ Enhancement Ideas

### 1. Auto-Execute Mode
Modify `/llm/steps` to optionally execute immediately:

```python
@app.post("/llm/steps")
async def receive_llm_steps(request: Request, auto_execute: bool = False):
    data = await request.json()
    
    if auto_execute:
        # Execute immediately
        results = []
        for step in data['steps']:
            result = run_cycle(user_task=step['action'])
            results.append(result)
        return {"status": "executed", "results": results}
    else:
        return {"status": "received", "steps": data['steps']}
```

### 2. Queue-Based Execution
Store steps in queue, process asynchronously:

```python
from queue import Queue
step_queue = Queue()

@app.post("/llm/steps")
async def receive_llm_steps(request: Request):
    data = await request.json()
    step_queue.put(data)  # Add to queue
    return {"status": "queued"}

# Background worker processes queue
```

### 3. Step-by-Step Execution
Execute one step, wait for confirmation, continue:

```python
@app.post("/llm/next-step")
async def execute_next_step():
    # Get next step from current plan
    # Execute it
    # Wait for frontend confirmation
    # Continue to next
```

---

## 📝 Summary

| Component | Status | Purpose |
|-----------|--------|---------|
| **LLM Generation** | ✅ Working | Generates multi-step plans |
| **Auto-Send** | ✅ Working | Sends to backend (200 OK) |
| **Backend Receive** | ✅ Working | Logs and acknowledges |
| **Auto-Execute** | ⚠️ Manual | Requires calling `/llm/execute` |
| **Single-Step** | ✅ Working | Via `/run-cycle` |

### To Execute Steps:
1. **Automatic send:** Already happening! ✅
2. **Manual execute:** Use `test_llm_flow.py` or call `/llm/execute`
3. **Single actions:** Use `/run-cycle` endpoint

---

## 🎯 Your Workflow

```bash
# Terminal 1: Start backend
uvicorn backend.main:app --reload

# Terminal 2: Generate steps (auto-sends)
python -m llm.interactive_generate
> Enter instruction: your task here

# Terminal 3: Execute steps (manual)
python test_llm_flow.py
```

**That's it!** Your LLM-generated steps are now integrated with the agentic AI backend! 🎉
