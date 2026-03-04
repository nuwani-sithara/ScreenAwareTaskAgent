# Google Gemini API Integration - FREE & FAST

## Why Gemini?

✅ **FREE** - Generous free tier (1500 requests/day)  
✅ **FAST** - 2-5 seconds (similar to ChatGPT, faster than Ollama)  
✅ **NO CREDIT CARD** - Free tier doesn't require payment  
✅ **Same interface** - Drop-in replacement for Ollama/OpenAI

## Speed & Cost Comparison

| Provider | Speed | Cost | Setup |
|----------|-------|------|-------|
| **Gemini 1.5 Flash** | 2-4s | **FREE** | Just API key |
| ChatGPT 4.0 Turbo | 2-5s | $0.01-0.03/req | API key + billing |
| Ollama Mistral | 15-45s | Free | Local install |

**Recommendation:** Use Gemini for fast, free responses!

## Setup (3 Steps)

### 1. Get FREE API Key

1. Go to https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key (starts with `AIza...`)

**No credit card required!**

### 2. Install Gemini Library

```bash
pip install google-generativeai
```

### 3. Use in Postman

**Method A: Pass API key in request**
```json
POST http://localhost:8002/llm/generate_hid

{
  "instruction": "Click the login button",
  "visual_data": {
    "session_data": {
      "screens": [{
        "elements": [
          {"elem_id": "elem_0", "label": "Login", "dx": 400, "dy": 300}
        ]
      }]
    }
  },
  "use_gemini": true,
  "gemini_api_key": "AIza-YOUR-KEY-HERE",
  "gemini_model": "gemini-1.5-flash"
}
```

**Method B: Set environment variable**
```powershell
# Windows PowerShell
$env:GEMINI_API_KEY = "AIza-YOUR-KEY-HERE"
```

Then just use:
```json
{
  "instruction": "Click login",
  "visual_data": {...},
  "use_gemini": true
}
```

## Available Models

| Model | Speed | Quality | Free Limit |
|-------|-------|---------|------------|
| `gemini-1.5-flash` | Fastest (2-3s) | Excellent | 1500/day |
| `gemini-1.5-pro` | Fast (3-5s) | Best | 1500/day |
| `gemini-pro` | Fast (3-4s) | Good | 60/min |

**Default:** `gemini-1.5-flash` (best balance)

## Complete Example

```json
POST http://localhost:8002/llm/generate_hid
Content-Type: application/json

{
  "instruction": "Type 'admin' in username field and click login",
  "visual_data": {
    "session_data": {
      "screens": [{
        "elements": [
          {
            "elem_id": "elem_0",
            "label": "Username",
            "type": "input_field",
            "dx": 512,
            "dy": 200
          },
          {
            "elem_id": "elem_1",
            "label": "Login",
            "type": "button",
            "dx": 512,
            "dy": 300
          }
        ]
      }]
    }
  },
  "use_gemini": true,
  "gemini_api_key": "AIza-YOUR-KEY-HERE",
  "gemini_model": "gemini-1.5-flash",
  "skip_validation": true
}
```

**Expected Response (2-4 seconds):**
```json
{
  "status": "success",
  "action_steps": [
    {"step": 1, "action": "click", "target": "Username", "x": 512, "y": 200},
    {"step": 2, "action": "type_text", "target": "Username", "text": "admin"},
    {"step": 3, "action": "click", "target": "Login", "x": 512, "y": 300}
  ],
  "hid_commands": [
    {"cmd": "mouse_move", "dx": 512, "dy": 200, "smooth": true},
    {"cmd": "mouse_click", "button": "left"},
    {"cmd": "type_text", "text": "admin"},
    {"cmd": "mouse_move", "dx": 512, "dy": 300, "smooth": true},
    {"cmd": "mouse_click", "button": "left"}
  ],
  "total_commands": 5
}
```

## Free Tier Limits

**Gemini 1.5 Flash (Recommended):**
- 1500 requests per day
- 1 million tokens per minute
- 15 requests per minute

**For your use case:** ~1500 tests/day is plenty!

## Error Handling

### Error: "API key not valid"
1. Check key starts with `AIza`
2. Verify at https://makersuite.google.com/app/apikey
3. Make sure API is enabled

### Error: "google-generativeai not installed"
```bash
pip install google-generativeai
```

### Error: "Resource exhausted"
You hit the free limit. Wait 24 hours or upgrade.

## Speed Optimization Tips

### Skip Validation (50% faster)
```json
{
  "instruction": "...",
  "visual_data": {...},
  "use_gemini": true,
  "skip_validation": true  // ← Saves 1 LLM call
}
```

**With validation:** 5-8 seconds  
**Without validation:** 2-4 seconds

### Use Flash Model (Fastest)
```json
{
  "use_gemini": true,
  "gemini_model": "gemini-1.5-flash"  // ← Fastest free model
}
```

## Quick Test

**Test Gemini client directly:**
```bash
cd llm
python gemini_client.py "AIza-YOUR-KEY-HERE"
```

**Test via API:**
```powershell
# Set API key
$env:GEMINI_API_KEY = "AIza-YOUR-KEY-HERE"

# Start API server
python -m uvicorn llm.api:app --reload --port 8002
```

Then test in Postman.

## Comparison Summary

| Feature | Gemini | ChatGPT | Ollama |
|---------|--------|---------|--------|
| **Speed** | ⚡ Fast (2-4s) | ⚡ Fast (2-5s) | 🐌 Slow (15-45s) |
| **Cost** | 💚 FREE | 💰 $0.01-0.03/req | 💚 FREE |
| **Setup** | ✅ API key only | ⚠️ API key + billing | 🔧 Local install |
| **Limits** | 1500/day free | Unlimited (paid) | Unlimited (local) |
| **Quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## My Recommendation

**For Development/Testing:**
→ **Use Gemini 1.5 Flash** (free, fast, 1500/day is plenty)

**For Production:**
→ **Use Gemini 1.5 Pro** (still free, best quality)

**For High Volume:**
→ Use ChatGPT 4.0 Turbo (unlimited but paid)

**For Offline/Privacy:**
→ Use Ollama (local, slower)

## Summary

✅ **Same process** - No workflow changes  
✅ **Just add** `"use_gemini": true`  
✅ **5-10x faster** than Ollama  
✅ **FREE** - No credit card  
✅ **1500 requests/day** - Plenty for testing  

Get your free API key: https://makersuite.google.com/app/apikey
