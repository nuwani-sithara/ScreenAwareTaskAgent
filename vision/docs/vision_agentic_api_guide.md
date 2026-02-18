# Vision API Guide for Agentic-AI Integration

## Base
- Service: `FastAPI` app in `src/api.py`
- Typical run command:
  - `uvicorn src.api:app --host 0.0.0.0 --port 8000`
- Base URL:
  - `http://localhost:8000`

## Core Endpoints

### 1) Start Continuous Vision
- `POST /vision/start`
- Query params:
  - `camera_index` (int, default `0`)
  - `save_interval` (float seconds, default `1.0`)
  - `provider` (`local` | `ollama` | `claude` | `gpt4v`)
  - `local_model` (string model id)
  - `ollama_base_url` (optional, example `http://127.0.0.1:11434`)
  - `no_vlm` (bool, default `false`)
- Returns:
  - `status`, `session_id`, `session_root`, model/provider settings

Example:
```bash
curl -X POST "http://localhost:8000/vision/start?provider=ollama&local_model=llava:7b&save_interval=1.0"
```

### 2) Stream Processed Results (SSE)
- `GET /vision/stream`
- Optional query:
  - `session_id` to filter one active session
- Content type:
  - `text/event-stream`
- Event payload (`data:` JSON):
  - success: `status=completed`, `vision_data`, `final_json_path`, `source_frame`
  - error: `status=error`, `detail`

Example:
```bash
curl -N "http://localhost:8000/vision/stream"
```

### 3) Stop Continuous Vision
- `POST /vision/stop`
- Optional query:
  - `session_id` (safety check)
- Returns summary counts:
  - `raw_frames`, `preprocessed_frames`, `coarse_json`, `refined_json`, `refined_debug_images`, `final_json`

Example:
```bash
curl -X POST "http://localhost:8000/vision/stop"
```

### 4) Single-Shot Capture + Process
- `POST /vision/capture`
- Same key params as `/vision/start` (except `save_interval`)
- Returns full result for one frame directly

Example:
```bash
curl -X POST "http://localhost:8000/vision/capture?provider=ollama&local_model=llava:7b"
```

### 5) Service Status
- `GET /vision/status`
- Returns if streaming is running and current session/provider details

Example:
```bash
curl "http://localhost:8000/vision/status"
```

## Session Artifact Layout
Each run creates `data/sessions/<session_id>/`:
- `raw_frames/`
- `preprocessed_frames/`
- `coarse_bboxes/` (`*.json`)
- `refined_bboxes/` (`*.json`)
- `refined_bboxes/debug/` (`*.jpg` annotated with refined boxes)
- `final_elements/` (`*.json`)
- `processing/` (per-frame isolated working folders)

## Recommended Agentic-AI Flow
1. Call `POST /vision/start`.
2. Subscribe to `GET /vision/stream?session_id=<id>`.
3. For each `completed` event:
   - Consume `vision_data.elements`.
   - Optionally read `final_json_path` for persisted artifact.
4. When done, call `POST /vision/stop?session_id=<id>`.

## Ollama Setup Notes
1. Install Ollama on the vision host.
2. Pull a vision-capable model (example):
   - `ollama pull llava:7b`
3. Start vision using:
   - `provider=ollama`
   - `local_model=<ollama-model-tag>` (example `llava:7b`)
4. If Ollama runs on non-default URL, pass:
   - `ollama_base_url=http://host:11434`
