# Quick Start Guide - Generalized Vision Perception

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd src
pip install -r requirements.txt
```

**Key new packages:**
- `anthropic` - Claude Vision
- `openai` - GPT-4V
- `transformers` - Local VLM models

### 2. Set Up API Keys

```bash
# Claude (Anthropic)
export ANTHROPIC_API_KEY="sk-ant-..."

# Or GPT-4V (OpenAI)
export OPENAI_API_KEY="sk-..."
```

### 3. Process Your First Image

```bash
cd src
python perception_pipeline.py \
    --image path/to/screenshot.jpg \
    --provider claude \
    --strategy hybrid
```

**Output files:**
- `screenshot_perception_output.json` - Detection results
- `screenshot_annotated.jpg` - Visualization

### 4. View Results

```json
{
  "detection": {
    "num_elements": 15,
    "elements": [
      {
        "id": "elem_0",
        "type": "button",
        "label": "Login",
        "bbox": [0.35, 0.7, 0.65, 0.85],
        "confidence": 0.95
      },
      ...
    ]
  },
  "semantic_state": {
    "interactive_elements": [...],
    "summary": {
      "actionable_elements": 3,
      "input_elements": 2
    }
  }
}
```

---

## Python API Usage

### Minimal Example

```python
from perception_pipeline import IntegratedPerceptionPipeline

# Initialize
pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")

# Process image
result = pipeline.process_image(
    "screenshot.jpg",
    strategy="hybrid"
)

# Access results
for element in result["detection"]["elements"]:
    print(f"{element['type']}: {element['label']}")
    print(f"  Position: {element['bbox']}")
    print(f"  Confidence: {element['confidence']:.1%}")
```

### Advanced Example

```python
from perception import PerceptionRouter, FeedbackLogger
from interpretation.semantic_state_builder import SemanticStateBuilder

# Setup
router = PerceptionRouter(
    vlm_provider="claude",
    yolo_model_path="best.pt",
    use_vlm=True,
    use_yolo=True
)
state_builder = SemanticStateBuilder()
logger = FeedbackLogger()

# Detect
result = router.detect("image.jpg", strategy="hybrid", refine=True)

# Build state
state = state_builder.build_semantic_state(result.elements)

# Find clickable elements
clickable = state_builder.find_clickable_elements(state, min_confidence=0.7)

# Log for feedback
event_id = logger.log_detection(
    "image.jpg",
    result.elements,
    action="click",
    target_element_id=clickable[0].id
)

# User feedback (after action completes)
logger.mark_feedback(event_id, success=True, reason="Navigation successful")
```

---

## Choosing a Strategy

### ✅ Use "hybrid" (default)
- Best performance/accuracy trade-off
- YOLO handles known patterns fast
- VLM handles unknown UIs
- **Recommended for most cases**

### ✅ Use "vlm" only
- New, unknown UI types
- High accuracy needed
- Time not critical
- **Recommended for exploration/research**

### ✅ Use "yolo" only
- Fast processing needed
- UI patterns already trained
- Cost/API budget limited
- **Recommended for known game/app**

---

## Command-Line Usage

### Single Image
```bash
python src/perception_pipeline.py \
    --image screenshot.jpg \
    --provider claude \
    --strategy hybrid
```

### With YOLO Model
```bash
python src/perception_pipeline.py \
    --image screenshot.jpg \
    --provider claude \
    --yolo-model runs/2048_ui/yolo_train2/weights/best.pt \
    --strategy hybrid
```

### Without Refinement (Faster)
```bash
python src/perception_pipeline.py \
    --image screenshot.jpg \
    --provider claude \
    --no-refine
```

### View Statistics
```bash
python src/perception_pipeline.py \
    --provider claude \
    --stats
```

---

## Workflow Examples

### Example 1: Batch Process Screenshots

```python
import glob
from perception_pipeline import IntegratedPerceptionPipeline

pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")

for image_path in glob.glob("screenshots/*.jpg"):
    print(f"Processing {image_path}...")
    result = pipeline.process_image(image_path)
    
    if result["success"]:
        count = result["detection"]["num_elements"]
        print(f"  ✓ Found {count} elements")

# Show statistics
stats = pipeline.get_statistics()
print(f"\nSuccess rate: {stats['success_rate']:.1%}")
```

### Example 2: Real-time Detection

```python
import cv2
from perception import PerceptionRouter

router = PerceptionRouter(vlm_provider="claude")

cap = cv2.VideoCapture("phone_screen.mp4")
frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame_path = f"temp_frame.jpg"
    cv2.imwrite(frame_path, frame)
    
    # Detect every 5 frames
    if frame_count % 5 == 0:
        result = router.detect(frame_path, strategy="hybrid")
        print(f"Frame {frame_count}: {len(result.elements)} elements")
        
        # Draw on frame
        for elem in result.elements:
            # ... draw bounding boxes
            pass
    
    frame_count += 1
```

### Example 3: Semantic State Queries

```python
from perception_pipeline import IntegratedPerceptionPipeline

pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")
result = pipeline.process_image("screenshot.jpg")

state = result["semantic_state"]

# Find all buttons
buttons = state_builder.find_clickable_elements(state)
print(f"Clickable buttons: {len(buttons)}")

# Find all inputs
inputs = state_builder.find_input_elements(state)
print(f"Input fields: {len(inputs)}")

# Find element by label
login_btn = state_builder.get_element_by_label(state, "Login")
if login_btn:
    print(f"Found login button at: {login_btn.bbox}")

# Find element at position
elem = state_builder.get_element_at_position(state, 0.5, 0.5)
if elem:
    print(f"Element at center: {elem.label}")
```

---

## Expected Performance

| Operation | Time | Cost |
|-----------|------|------|
| YOLO detection (single image) | 100-300ms | ~$0.00 |
| VLM detection (Claude) | 2-5 seconds | ~$0.02 |
| Grounding refinement | 200-500ms | $0.00 |
| Semantic state building | 50-100ms | $0.00 |

---

## Common Issues & Solutions

### ❌ "ANTHROPIC_API_KEY not set"
```bash
# Set environment variable
export ANTHROPIC_API_KEY="sk-ant-..."

# Or pass directly
router = PerceptionRouter(
    vlm_provider="claude",
    vlm_kwargs={"api_key": "sk-ant-..."}
)
```

### ❌ "No module named 'anthropic'"
```bash
# Install dependencies
pip install anthropic openai transformers

# Or install full requirements
pip install -r src/requirements.txt
```

### ❌ "Image too large"
VLM APIs have image size limits. Resize before sending:
```python
from perception.vlm import VLMClient

# Most APIs handle up to 4096x4096
# Consider downsampling very large images
import cv2
image = cv2.imread("large_image.jpg")
resized = cv2.resize(image, (1920, 1080))
cv2.imwrite("resized.jpg", resized)
```

### ❌ "YOLO model not found"
```python
# Either provide path
router = PerceptionRouter(
    yolo_model_path="/absolute/path/to/best.pt"
)

# Or disable YOLO
router = PerceptionRouter(use_yolo=False)
```

---

## Next Steps

1. **Run the pipeline** on a few screenshots
2. **Compare strategies** (vlm vs yolo vs hybrid)
3. **Integrate with agent** using the `semantic_state`
4. **Collect feedback** to enable weak supervision
5. **Monitor statistics** and iterate

---

## Support

For more detailed information, see:
- [PERCEPTION_SYSTEM.md](PERCEPTION_SYSTEM.md) - Full documentation
- [src/perception/](../src/perception/) - Source code
- API documentation links in main guide
