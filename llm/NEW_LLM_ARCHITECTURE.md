# LLM Architecture - Screen-Aware Task Agent

## Overview

The LLM service is a FastAPI microservice that converts natural language instructions + visual screen data into executable HID (Human Interface Device) protocol commands for automated task execution.

**Port:** 8002  
**Framework:** FastAPI  
**Primary LLM:** Google Gemini (FREE)  
**Fallback LLM:** Ollama (local)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT (Postman/Frontend)               │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ POST /llm/generate_hid
                            │ {instruction, visual_data, use_gemini}
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Service (api.py)                  │
│                         Port: 8002                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ Select LLM Client
                            ▼
        ┌───────────────────┴──────────────────┐
        │                                      │
        ▼                                      ▼
┌──────────────────┐                  ┌──────────────────┐
│  GeminiClient    │                  │  OllamaClient    │
│  (gemini_client) │                  │ (ollama_client)  │
│                  │                  │                  │
│ • API: Gemini    │                  │ • API: Local     │
│ • Speed: 2-4s    │                  │ • Speed: 15-45s  │
│ • Cost: FREE     │                  │ • Cost: FREE     │
│ • Model:         │                  │ • Model:         │
│   gemini-flash   │                  │   mistral        │
└──────────────────┘                  └──────────────────┘
        │                                      │
        └───────────────────┬──────────────────┘
                            │
                            │ generate(prompt, model, max_tokens)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│            HIDStepGenerator (hid_step_generator.py)         │
│                    Three-Stage Pipeline                     │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌────────────────┐   ┌──────────────┐
│   Stage 0    │   │    Stage 1     │   │   Stage 2    │
│  Validation  │   │ Action Steps   │   │ HID Commands │
│  (optional)  │   │   (JSON)       │   │  (Protocol)  │
└──────────────┘   └────────────────┘   └──────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
    ┌────────┐      ┌────────────┐      ┌──────────────┐
    │is_valid│      │[{step: 1,  │      │[{cmd: "mouse│
    │reason  │      │  action:   │      │   _move",    │
    │missing │      │  "click",  │      │   dx: 863,   │
    │elements│      │  target:   │      │   dy: 475},  │
    └────────┘      │  "Login"}] │      │ {cmd: "click│
                    └────────────┘      │  "}]         │
                                        └──────────────┘
```

---

## LLM Provider Selection

### Decision Flow

```python
if request.use_gemini:
    client = GeminiClient(api_key=request.gemini_api_key)
    model = request.gemini_model or "models/gemini-flash-latest"
else:
    client = OllamaClient()
    model = "mistral"
```

### Provider Comparison

| Provider | Speed | Cost | Use Case | Status |
|----------|-------|------|----------|--------|
| **Gemini** | 2-4s | FREE (1500/day) | Production (recommended) | ✅ Active |
| **Ollama** | 15-45s | FREE (unlimited) | Offline/Development | ✅ Active |

---

## Three-Stage Pipeline

### Stage 0: Validation (Optional)

**Purpose:** Verify instruction matches available UI elements before generating actions.

**Input:**
```json
{
  "instruction": "Click login button",
  "visual_data": {"screens": [{"elements": [...]}]}
}
```

**LLM Prompt:**
```
Analyze whether the user's instruction can be completed with available elements.
Return: {is_valid: true/false, confidence: 0-1, reason: "...", missing_elements: [...]}
```

**Output:**
```json
{
  "is_valid": true,
  "confidence": 0.95,
  "reason": "Login button found at (400, 300)",
  "missing_elements": []
}
```

**Configuration:**
- Default: `skip_validation: false` (enabled)
- Can skip with: `"skip_validation": true` in request
- Reduces latency by ~3-5 seconds when skipped

---

### Stage 1: Action Generation

**Purpose:** Convert instruction + visual data → structured action steps (JSON).

**LLM Prompt:**
```
Generate step-by-step actions as JSON array:
[
  {"step": 1, "action": "click", "target": "Login", "x": 400, "y": 300},
  {"step": 2, "action": "type_text", "target": "Username", "text": "tharushi"}
]

Available actions: click, type_text, double_click, right_click, scroll, drag, press_key
```

**Example Output:**
```json
[
  {"step": 1, "action": "click", "target": "Username field", "x": 863, "y": 475},
  {"step": 2, "action": "type_text", "target": "Username field", "text": "tharushi"},
  {"step": 3, "action": "click", "target": "Password field", "x": 863, "y": 583},
  {"step": 4, "action": "type_text", "target": "Password field", "text": "123"},
  {"step": 5, "action": "click", "target": "Login button", "x": 912, "y": 739}
]
```

**Error Handling:**
- JSON parsing failure → Fallback to first detected element (click action)
- Truncated output (max_tokens too small) → Fallback action
- Empty response → Fallback action

---

### Stage 2: HID Command Conversion

**Purpose:** Convert action steps → HID protocol commands.

**Conversion Rules:**

| Action | HID Commands |
|--------|-------------|
| `click` | `mouse_move(dx, dy, smooth=true)` + `mouse_click(button="left")` |
| `type_text` | `type_text(text="...")` |
| `double_click` | `mouse_move(dx, dy)` + `mouse_click(button="left")` + `mouse_click(button="left")` |
| `right_click` | `mouse_move(dx, dy)` + `mouse_click(button="right")` |
| `scroll` | `mouse_scroll(direction="down", amount=...)` |
| `drag` | `mouse_move(start_x, start_y)` + `mouse_down()` + `mouse_move(end_x, end_y)` + `mouse_up()` |
| `press_key` | `key_press(key="Enter")` |

**Example Output:**
```json
[
  {"cmd": "mouse_move", "dx": 863, "dy": 475, "smooth": true, "meta": {...}},
  {"cmd": "mouse_click", "button": "left", "meta": {...}},
  {"cmd": "type_text", "text": "tharushi", "meta": {...}},
  {"cmd": "mouse_move", "dx": 863, "dy": 583, "smooth": true, "meta": {...}},
  {"cmd": "mouse_click", "button": "left", "meta": {...}},
  {"cmd": "type_text", "text": "123", "meta": {...}},
  {"cmd": "mouse_move", "dx": 912, "dy": 739, "smooth": true, "meta": {...}},
  {"cmd": "mouse_click", "button": "left", "meta": {...}}
]
```

**Metadata:**
- Each command gets unique `commandId` (UUID)
- Timestamp included for tracking
- Step reference for debugging

---

## Client Architecture

### Interface Contract

All LLM clients implement the same interface:

```python
class LLMClient:
    def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        **kwargs
    ) -> str:
        """Generate text from prompt"""
        pass
```

### Drop-in Replacement Pattern

```python
# All clients interchangeable
client = GeminiClient()  # or OllamaClient()
response = client.generate(prompt="...", model="...", max_tokens=1500)
```

### Lazy Import Pattern

```python
def _ensure_genai(self):
    """Import library only when needed"""
    if self._genai is None:
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError("Install with: pip install google-generativeai")
```

**Benefits:**
- No crash if library not installed
- Only import when actually used
- Clean error messages

---

## Configuration

### Environment Variables

```bash
# Required for Gemini
GEMINI_API_KEY=AIzaSy...

# Optional (can pass in request instead)
GEMINI_MODEL_NAME=models/gemini-flash-latest
```

### Request Parameters

```json
{
  "instruction": "Click login",
  "visual_data": {...},
  
  // LLM Provider
  "use_gemini": true,                        // Use Gemini (default: false = Ollama)
  "gemini_api_key": "AIza...",               // API key (or use env var)
  "gemini_model": "models/gemini-flash-latest", // Model (default: gemini-2.5-flash)
  
  // Generation Settings
  "max_tokens": 1500,                        // Max response length (default: 1500)
  "skip_validation": false,                  // Skip validation stage (default: false)
  
  // Legacy (for Ollama)
  "model": "mistral"                         // Ollama model (when not using Gemini)
}
```

### Defaults

| Parameter | Default Value | Notes |
|-----------|--------------|-------|
| `max_tokens` | 1500 | Changed from 300 → 500 → 1500 |
| `gemini_model` | `models/gemini-2.5-flash` | Fastest Gemini model |
| `skip_validation` | `false` | Validation enabled by default |
| `use_gemini` | `false` | Falls back to Ollama if not set |

---

## API Endpoints

### POST /llm/generate_hid

**Main endpoint for HID command generation**

**Request:**
```json
{
  "instruction": "Enter username 'tharushi' and password '123' then login",
  "visual_data": {
    "session_data": {
      "screens": [{
        "elements": [
          {"type": "input", "label": "Username", "dx": 863, "dy": 475},
          {"type": "input", "label": "Password", "dx": 863, "dy": 583},
          {"type": "button", "label": "Login", "dx": 912, "dy": 739}
        ]
      }]
    }
  },
  "use_gemini": true,
  "skip_validation": false
}
```

**Response:**
```json
{
  "status": "success",
  "instruction": "...",
  "validation": {
    "is_valid": true,
    "confidence": 1.0,
    "reason": "All elements present"
  },
  "rewritten_steps": [
    {"step": 1, "action": "click", "description": "Click Username"},
    {"step": 2, "action": "type_text", "description": "Type 'tharushi'"},
    ...
  ],
  "action_steps": [...],
  "hid_commands": [...],
  "total_commands": 8,
  "execution_time": "11.08s"
}
```

### GET /llm/health

**Health check endpoint**

**Response:**
```json
{
  "status": "healthy",
  "service": "LLM Step Generation Service",
  "version": "2.0.0",
  "ollama_available": true,
  "timestamp": "2026-03-04T08:36:41Z"
}
```

---

## File Structure

```
llm/
├── api.py                      # FastAPI service (port 8002)
├── gemini_client.py            # Google Gemini client
├── ollama_client.py            # Ollama local client
├── hid_step_generator.py       # Three-stage pipeline
├── requirements.txt            # Dependencies
│
├── GEMINI_INTEGRATION.md       # Gemini setup guide
├── POSTMAN_GEMINI_EXAMPLES.md  # API usage examples
├── NEW_LLM_ARCHITECTURE.md     # This file
│
└── __pycache__/
```

---

## Performance Benchmarks

### Execution Time (Complex 5-step Task)

| Configuration | Time | Notes |
|--------------|------|-------|
| **Gemini + Validation** | 11s | Recommended for production |
| **Gemini + Skip Validation** | 6-7s | Fastest (use when confident) |
| **Ollama + Validation** | 30-50s | Slow but offline |
| **Ollama + Skip Validation** | 15-20s | Offline fallback |

### Stage Breakdown (Gemini)

| Stage | Time | % |
|-------|------|---|
| Validation (Stage 0) | 3-4s | 35% |
| Action Generation (Stage 1) | 3-4s | 35% |
| HID Conversion (Stage 2) | <0.1s | 1% |
| Network/Overhead | 1-2s | 15% |
| **Total** | **11s** | **100%** |

---

## Error Handling

### Validation Failure

**Response:**
```json
{
  "status": "validation_failed",
  "message": "Submit Form button not found on screen",
  "validation": {
    "is_valid": false,
    "confidence": 0.0,
    "missing_elements": ["Submit Form button"]
  },
  "suggested_actions": [
    "Check if the element exists",
    "Try a different selector",
    "Skip validation if you're sure"
  ]
}
```

### JSON Parse Failure

**Behavior:**
- Falls back to first detected UI element
- Generates simple click action
- Logs error with raw LLM output

**Example:**
```
ERROR: Failed to parse LLM output as JSON: Unterminated string
WARNING: Stage 1 returned no actions - generating fallback action
INFO: Generated fallback action: click Username at (863, 475)
```

### API Key Missing

**Response:**
```json
{
  "detail": "Gemini API key not set. Set GEMINI_API_KEY env var or pass to constructor."
}
```

### Library Not Installed

**Response:**
```json
{
  "detail": "google-generativeai library required for GeminiClient. Install with: pip install google-generativeai"
}
```

---

## Security Considerations

### API Key Management

✅ **Best Practices:**
- Store in environment variable (`GEMINI_API_KEY`)
- Never commit to version control
- Use system-level environment variables for production

❌ **Avoid:**
- Hardcoding in source files
- Sharing in chat/public forums (keys get auto-revoked)
- Storing in plaintext config files

### Request Validation

- All requests validated via Pydantic models
- Visual data structure verified
- Instruction length limits enforced

---

## Future Enhancements

### Planned Features

1. **Multi-provider Support**
   - Keep Gemini + Ollama
   - Add Claude, GPT-4 as optional providers

2. **Caching Layer**
   - Cache validation results for repeated instructions
   - Cache action plans for common patterns

3. **Streaming Responses**
   - Stream HID commands as they're generated
   - Reduce perceived latency

4. **Context Memory**
   - Remember previous actions in session
   - Enable multi-turn conversations

5. **Custom Prompts**
   - User-configurable system prompts
   - Domain-specific action vocabularies

---

## Troubleshooting

### Issue: "max_tokens=500 still shown in logs"

**Cause:** Hardcoded values in `hid_step_generator.py`  
**Fix:** Updated all 4 locations to use 1500

### Issue: "Only 1 step generated instead of 5"

**Cause:** Response truncated due to low max_tokens  
**Fix:** Increased default from 500 → 1500

### Issue: "Gemini API not being used"

**Cause:** `use_gemini: true` not in request OR GEMINI_API_KEY not set  
**Fix:** Add to request body and verify env var

### Issue: "Validation always fails"

**Cause:** Instruction doesn't match visual elements  
**Fix:** Use `"skip_validation": true` or fix instruction/visual_data

---

## Changelog

### v2.0.0 (March 4, 2026)
- ✅ Added Gemini API support (FREE, 2-4s response)
- ✅ Removed OpenAI support (user preference for free solutions)
- ✅ Increased max_tokens: 300 → 1500
- ✅ Fixed JSON truncation issues
- ✅ Updated default model: `models/gemini-flash-latest`

### v1.0.0 (Initial)
- ✅ Ollama local LLM support
- ✅ Three-stage pipeline (validation → actions → HID)
- ✅ FastAPI microservice architecture
- ✅ HID protocol command generation

---

## Contact & Support

**Developer:** ScreenAwareTaskAgent Team  
**LLM Service Port:** 8002  
**Documentation:** See `llm/GEMINI_INTEGRATION.md` for setup  
**Examples:** See `llm/POSTMAN_GEMINI_EXAMPLES.md` for API usage
