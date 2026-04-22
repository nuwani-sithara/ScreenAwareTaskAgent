# Vision Component — Architecture & Docs ✅

## Overview
This document explains the Vision microservice (FastAPI) used by the agentic core to capture screen frames, run a CV pipeline, and return structured JSON representing detected UI elements and OCR text.

## High-level components
- **API (src/api.py)** — FastAPI endpoints and orchestration:
  - POST `/vision/start` — start session-based capture (camera_index=1)
  - POST `/vision/stop` — stop capture, run pipeline (preprocess → detect → extract), return JSON
  - POST `/vision/capture` — save a single frame; with `?run_pipeline=true` runs full pipeline for the shot
- **Capture (src/capture/webcam_capture.py)** — generator-style webcam stream and helper capture methods.
- **Change Detection** — small-grayscale resize + absdiff + threshold to save frames only on UI change.
- **Preprocessing (src/preprocessing/preprocess.py)** — crop/resize/CLAHE, supports session paths.
- **Detection (src/detection/yolo_detect.py)** — YOLOv8 (Ultralytics) inference; outputs annotated images and CSVs of boxes.
- **Interpretation / OCR (src/interpretation/extract_state2.py)** — uses multi-variant Tesseract configs, bbox expansion, CLAHE/sharpen/deskew, and EasyOCR fallback to create `vision_data.json`.
- **Session storage (vision/data/sessions/)** — per-run folders keeping `raw_frames`, `preprocessed_frames`, `detected_images`, `detected_csvs`, `final_output`.

## Data flow
1. Agentic core calls `/vision/start` → API creates session and starts capture.
2. Capture loop streams frames, change-detection saves only changed frames to the session `raw_frames/`.
3. On `/vision/stop` the API runs:
   - Preprocess raw frames → `preprocessed_frames`
   - YOLO detect → `detected_images` + `detected_csvs`
   - Extract/OCR → `final_output/vision_data.json`
4. The API returns the JSON body to the caller.

Single-shot: `/vision/capture?run_pipeline=true` creates a temporary shot session for one frame and runs the same pipeline, returning the JSON.

## Techniques & implementation notes
- **YOLOv8** (Ultralytics) for object detection.
- **OCR improvements** implemented:
  - Bounding box expansion (padding) to avoid clipped text
  - Upscaling small crops
  - CLAHE, bilateral filter, unsharp mask (sharpen)
  - Adaptive/Otsu threshold variations and deskew
  - Multiple Tesseract `--psm` variants + class-specific character whitelist
  - EasyOCR fallback when Tesseract confidence is low
  - PaddleOCR fallback (optional) for improved robustness on difficult crops; requires installing `paddleocr` and a compatible `paddlepaddle` build (CPU/GPU) per the PaddlePaddle installation guide
- **Change detection**: small grayscale images (max dim ~320), absdiff + binary threshold, compute fraction of changed pixels. Default: 1% threshold.

## Endpoints & expected responses
- POST `/vision/start` → {"status":"started","camera_index":0,"session_id":"session_..."}
- POST `/vision/capture` (no params while session active) → {"timestamp":..., "frame": {...}, "saved_frame":"path"}
- POST `/vision/capture?run_pipeline=true` (single-shot) → {"status":"completed","vision_data":{...},"session_id":"shot_..."}
- POST `/vision/stop?session_id=<id>` → {"status":"completed","vision_data":{...}}

## Run & test locally
1. In `vision/` venv activate, install dependencies: `pip install -r src/requirements.txt`.
2. Start service: `python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8001`.
3. Use FastAPI docs: `http://127.0.0.1:8001/docs` for manual testing.
4. Use backend helper: `from backend.core.perceive import perceive; perceive()` — runs start→wait→stop and returns `vision_data`.

## Diagrams
- Software architecture (component diagram): `vision/docs/software_architecture.puml`
- System architecture (deployment & external dependencies): `vision/docs/system_architecture.puml`

You can render `.puml` files with a PlantUML tool or the VS Code PlantUML extension to get visual diagrams.
## Debugging & evaluation
- Check logs for saved frames ("Frame saved: ...") when capturing.
- Inspect session folder `vision/data/sessions/<session_id>/` to view intermediate files.
- For OCR debugging: enable debug dumps (optionally add) to `vision/data/debug/` to save crops + candidate OCR outputs for manual inspection.

## Improvements / roadmap
1. Make `/vision/stop` run pipeline asynchronously (return a job id + status endpoint). ✅
2. Add `/vision/sessions` endpoints for listing, details and deletion.
3. Add metadata DB (SQLite) to track sessions, deduplicate frames across sessions, and for retention policies.
4. Add automated tests for single-shot and session flows.
5. Consider training a domain-specific OCR or using PaddleOCR if accuracy still inadequate.

---

If you'd like, I can also generate a simple PlantUML PNG (requires PlantUML locally) or add a `vision/docs/README.md` with quick start instructions and sample requests. Which one should I add next? 🧭