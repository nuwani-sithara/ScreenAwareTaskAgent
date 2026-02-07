# Vision Perception System - Generalized UI Detection with VLM

## Overview

The generalized vision perception system combines **Vision-Language Models (VLM)** with optional **YOLO fast-path** to detect and understand UI elements in any application—without requiring app-specific training.

### Key Architecture Change

**Before (YOLO-only):**
```
Screen → Capture → YOLO (trained) → coords → interpretation ❌ Limited to trained UI
```

**After (VLM-centric + optional YOLO):**
```
Screen → Capture → VLM/YOLO Router → Grounding (refine) → Interpretation → State ✅ General-purpose
```

---

## System Components

### 1. **Perception Router** (`src/perception/perception_router.py`)

Routes detection through the optimal pipeline:

- **Strategy: "vlm"** → VLM only (zero-shot, slow)
- **Strategy: "yolo"** → YOLO only (fast, limited)
- **Strategy: "hybrid"** (default) → VLM with YOLO fallback

```python
from perception import PerceptionRouter

router = PerceptionRouter(
    vlm_provider="claude",      # or "gpt4v", "local"
    yolo_model_path="best.pt",
    use_vlm=True,
    use_yolo=True
)

result = router.detect(
    "screenshot.jpg",
    strategy="hybrid",          # Try YOLO first, fall back to VLM
    refine=True                 # Apply grounding refinement
)
```

### 2. **VLM Client** (`src/perception/vlm/vlm_client.py`)

Supports multiple VLM providers:

#### Claude (Anthropic)
```python
from perception import get_vlm_client

client = get_vlm_client("claude")  # Uses ANTHROPIC_API_KEY
result = client.analyze_ui("screenshot.jpg")
```

#### GPT-4V (OpenAI)
```python
client = get_vlm_client("gpt4v")  # Uses OPENAI_API_KEY
result = client.analyze_ui("screenshot.jpg")
```

#### Local Models (LLaVA, Qwen)
```python
client = get_vlm_client("local", model_name="llava-1.5-7b-hf")
result = client.analyze_ui("screenshot.jpg")
```

### 3. **UI Parser** (`src/perception/vlm/ui_parser.py`)

Parses VLM JSON output into structured `UIElement` objects:

```python
from perception import UIParser, UIElement

parser = UIParser()
result = parser.parse_vlm_response(vlm_response, image_width, image_height)

# result.elements contains:
# - UIElement.type (button, input_field, text, etc.)
# - UIElement.bbox (normalized 0-1 coordinates)
# - UIElement.confidence
# - UIElement.state (active, disabled, focused, etc.)
```

### 4. **Grounding Layer**

#### BBox Refiner (`src/perception/grounding/bbox_refiner.py`)
- Snaps VLM bboxes to detected edges
- Applies grid alignment
- Validates element sizes

```python
from perception.grounding import BBoxRefiner

refiner = BBoxRefiner(edge_detection_method="canny")
refined_bbox = refiner.refine_bbox(image, bbox_normalized, use_edge_detection=True)
```

#### Overlap Resolver (`src/perception/grounding/overlap_resolver.py`)
- Merges overlapping detections
- Filters nested elements (false positives)
- Groups nearby elements

```python
from perception.grounding import OverlapResolver

resolver = OverlapResolver()

# Resolve overlaps
resolved_bboxes, resolved_ids = resolver.resolve_overlaps(
    bboxes,
    element_ids,
    iou_threshold=0.3,
    strategy="merge"
)

# Filter nested elements
filtered_bboxes, filtered_ids = resolver.filter_nested(bboxes, nesting_threshold=0.8)
```

### 5. **Semantic State Builder** (`src/interpretation/semantic_state_builder.py`)

Converts detected elements into semantic game/UI state:

```python
from interpretation.semantic_state_builder import SemanticStateBuilder

builder = SemanticStateBuilder()
semantic_state = builder.build_semantic_state(detected_elements)

# semantic_state contains:
# {
#   "elements": [...],
#   "groups": {"inputs": [...], "actions": [...], ...},
#   "input_pairs": [...],  # input + label pairs
#   "interactive_elements": [...],
#   "summary": {...}
# }
```

### 6. **Feedback Logger** (`src/perception/feedback_logger.py`)

Weak supervision feedback system for continuous improvement:

```python
from perception import FeedbackLogger

logger = FeedbackLogger()

# Log detection
event_id = logger.log_detection(
    image_path="screenshot.jpg",
    elements=detected_elements,
    action="click",
    target_element_id="button_123"
)

# Record feedback
logger.mark_feedback(
    event_id,
    success=True,  # Action worked
    reason="Successfully navigated to next screen"
)

# Get statistics
stats = logger.get_improvement_summary()

# Export as training data
dataset_path = logger.export_training_dataset(min_confidence=0.7)
```

---

## Usage Workflows

### Workflow 1: Simple Image Analysis

```python
from perception_pipeline import IntegratedPerceptionPipeline

pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")

result = pipeline.process_image(
    "screenshot.jpg",
    strategy="hybrid",
    save_output=True
)

print(f"Found {result['detection']['num_elements']} UI elements")
print(f"Actionable elements: {result['semantic_state']['summary']['actionable_elements']}")
```

### Workflow 2: Real-time Capture + Perception

```python
import cv2
from perception import PerceptionRouter

router = PerceptionRouter(vlm_provider="claude", use_yolo=True)

cap = cv2.VideoCapture(0)
frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Save frame
    frame_path = f"frame_{frame_count}.jpg"
    cv2.imwrite(frame_path, frame)
    
    # Detect (every 10 frames to save API calls)
    if frame_count % 10 == 0:
        result = router.detect(frame_path, strategy="hybrid", refine=True)
        print(f"Frame {frame_count}: {len(result.elements)} elements")
    
    frame_count += 1
```

### Workflow 3: Agent Interaction Loop

```python
from perception_pipeline import IntegratedPerceptionPipeline

pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")

# Take screenshot
screenshot = take_screenshot()  # Your capture function

# Detect UI
result = pipeline.process_image(screenshot, strategy="hybrid")

# Agent reasons about UI
clickable = [e for e in result.elements if e.type == "button"]
best_action = agent.decide_action(clickable)

# Execute action
execute_action(best_action)

# Record feedback
logger.mark_feedback(event_id, success=True, reason="Action completed")
```

### Workflow 4: Batch Processing with Statistics

```python
from perception_pipeline import IntegratedPerceptionPipeline

pipeline = IntegratedPerceptionPipeline()

# Process folder
for image_path in glob.glob("screenshots/*.jpg"):
    result = pipeline.process_image(image_path)
    if result["success"]:
        # Simulate user marking success
        pipeline.save_feedback(result["event_id"], True)

# View stats
stats = pipeline.get_statistics()
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Element types: {stats['element_types_seen']}")
```

---

## Configuration

### Environment Variables

```bash
# For Claude
export ANTHROPIC_API_KEY="sk-ant-..."

# For GPT-4V
export OPENAI_API_KEY="sk-..."
```

### Per-Request Configuration

```python
# Custom VLM settings
router = PerceptionRouter(
    vlm_provider="claude",
    vlm_kwargs={
        "model_name": "claude-3-opus-20240229",  # Custom model
        "api_key": "..."  # Override env var
    }
)

# Detection parameters
result = router.detect(
    "image.jpg",
    strategy="hybrid",
    vlm_prompt="Custom instructions...",  # Custom prompt
    yolo_conf=0.6,  # YOLO confidence
    min_vlm_confidence=0.5,  # VLM confidence
    refine=True
)
```

---

## File Structure

```
src/
├── perception/                      ⭐ NEW LAYER
│   ├── vlm/
│   │   ├── vlm_client.py           # VLM API clients
│   │   ├── ui_parser.py            # JSON parsing
│   │   ├── prompt_templates.py     # Prompts
│   │   └── __init__.py
│   │
│   ├── grounding/
│   │   ├── bbox_refiner.py         # BBox refinement
│   │   ├── overlap_resolver.py     # Overlap handling
│   │   └── __init__.py
│   │
│   ├── perception_router.py        # Main router
│   ├── feedback_logger.py          # Weak supervision
│   └── __init__.py
│
├── perception_pipeline.py           # ⭐ NEW - Integrated pipeline
│
├── capture/
│   ├── ipcam_capture.py
│   └── ...
│
├── detection/                       (now optional)
│   ├── yolo_detect.py              # Updated with perception support
│   └── yolo_train.py
│
├── interpretation/
│   ├── semantic_state_builder.py   # ⭐ NEW - General-purpose state
│   ├── state_builder.py            # (kept for backward compatibility)
│   └── ...
│
└── ...
```

---

## Performance Considerations

### Speed Trade-offs

| Strategy | Speed | Generalization | Cost |
|----------|-------|----------------|------|
| YOLO | ⚡ Fast (30 FPS) | ❌ Limited | 💰 Free |
| VLM | 🐢 Slow (1-2 FPS) | ✅ Excellent | 💸 API calls |
| Hybrid | ⚡ Fast (YOLO) + VLM fallback | ✅ Best of both | 💰 Balanced |

### Optimization Tips

1. **Use "hybrid" strategy** for best ROI
2. **Cache YOLO results** for known UI patterns
3. **Batch VLM calls** to reduce API overhead
4. **Use lower confidence thresholds** for exploration
5. **Apply grounding refinement** to improve accuracy

---

## Weak Supervision Loop (Self-Improvement)

The system can improve over time using feedback:

```python
# 1. Detect elements
result = pipeline.process_image("screenshot.jpg")

# 2. Agent acts on detection
action_result = execute_action(result)

# 3. Record success/failure
if action_result.success:
    pipeline.save_feedback(result["event_id"], True)
else:
    pipeline.save_feedback(result["event_id"], False, "Action failed")

# 4. Periodically export dataset
dataset = logger.export_training_dataset()
# Use for fine-tuning or validation
```

**Storage:**
- Positive feedback: `data/feedback/positive/`
- Negative feedback: `data/feedback/negative/`
- Sessions: `data/feedback/sessions/`
- Datasets: `data/feedback/training_dataset_*.json`

---

## Troubleshooting

### Issue: VLM returns empty response

**Solution:** Check API key and rate limits
```python
# Set custom timeout and retries
client = ClaudeVLMClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
# Claude has rate limiting; add delays between calls
```

### Issue: YOLO is faster but less accurate on new UI

**Solution:** Use hybrid strategy with lower YOLO threshold
```python
result = router.detect(
    "image.jpg",
    strategy="hybrid",
    yolo_conf=0.3,  # Lower threshold
    min_vlm_confidence=0.4  # Fallback more often
)
```

### Issue: BBoxes slightly off after refinement

**Solution:** Adjust grounding parameters
```python
result = router.refine_detections(
    "image.jpg",
    raw_result,
    use_edge_snap=True,
    use_grid_snap=True,  # Enable grid alignment
    grid_size=8  # Adjust grid size
)
```

---

## API Reference

### PerceptionRouter

```python
class PerceptionRouter:
    def detect(self, image_path: str, strategy="hybrid", ...) -> UIAnalysisResult
    def refine_detections(self, image_path: str, result: UIAnalysisResult, ...) -> UIAnalysisResult
    def detect_changes(self, image1: str, image2: str) -> Dict
```

### UIElement

```python
@dataclass
class UIElement:
    id: str
    type: str  # button, input_field, text, icon, etc.
    label: str
    description: str
    state: str  # active, disabled, focused, etc.
    bbox: Tuple[float, float, float, float]  # normalized 0-1
    confidence: float  # 0-1
```

### FeedbackLogger

```python
class FeedbackLogger:
    def log_detection(...) -> str  # Returns event_id
    def mark_feedback(event_id: str, success: bool, ...)
    def get_element_statistics() -> Dict
    def export_training_dataset(...) -> str
    def get_improvement_summary() -> Dict
```

---

## Next Steps

1. **Test with different VLM providers** (Claude, GPT-4V, local)
2. **Fine-tune prompts** for your specific use case
3. **Collect feedback** to enable weak supervision
4. **Integrate with agent** for closed-loop learning
5. **Monitor and iterate** based on statistics

---

## References

- **Claude Vision**: https://docs.anthropic.com/en/docs/vision/overview
- **GPT-4V**: https://platform.openai.com/docs/guides/vision
- **LLaVA**: https://llava-vl.github.io/
- **YOLO**: https://docs.ultralytics.com/
