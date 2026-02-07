# Migration Guide - From YOLO-Only to Hybrid VLM Perception

## Overview

This guide helps you migrate from the old YOLO-only detection system to the new generalized VLM + optional YOLO hybrid system.

**Good news:** ✅ **Backward compatible** - Old code still works, but you can gradually adopt new features.

---

## Before → After Comparison

### Old Way (YOLO-Only)

```python
# OLD: YOLO-specific workflow
from detection.yolo_detect import run_detection

# 1. Run detection on preprocessed frames
run_detection(
    preprocessed_folder="data/preprocessed_frames",
    output_img_folder="data/detected_images",
    output_csv_folder="data/detected_csvs",
    model_path="best.pt"
)

# 2. Parse CSV results manually
import pandas as pd
detections = pd.read_csv("detected_csvs/frame_123.csv")

# 3. Manually interpret results
for _, row in detections.iterrows():
    bbox = (row['x_min'], row['y_min'], row['x_max'], row['y_max'])
    # ... process each detection
```

**Problems:**
- ❌ Only works on trained UI
- ❌ Need to retrain for new apps
- ❌ No semantic understanding
- ❌ Brittle on UI variations

### New Way (Hybrid VLM + YOLO)

```python
# NEW: Generalized perception workflow
from perception_pipeline import IntegratedPerceptionPipeline

# 1. Initialize once
pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")

# 2. Process images (any UI!)
result = pipeline.process_image(
    "screenshot.jpg",
    strategy="hybrid",  # VLM + optional YOLO
    save_output=True
)

# 3. Access semantic state
state = result["semantic_state"]

# 4. Query intelligently
for elem in state["interactive_elements"]:
    print(f"{elem['type']}: {elem['label']}")
```

**Benefits:**
- ✅ Works on ANY UI
- ✅ No retraining needed
- ✅ Semantic understanding
- ✅ Robust to variations
- ✅ Self-improving with feedback

---

## Step-by-Step Migration

### Phase 1: Setup (No Code Changes)

**1.1 Install New Dependencies**

```bash
cd src
pip install -r requirements.txt
```

New packages added:
- `anthropic` - Claude Vision
- `openai` - GPT-4V (optional)
- `transformers` - Local VLMs (optional)

**1.2 Set API Keys**

```bash
# For Claude
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional: For GPT-4V
export OPENAI_API_KEY="sk-..."
```

**1.3 Verify Installation**

```python
# Test imports
from perception import PerceptionRouter
from interpretation.semantic_state_builder import SemanticStateBuilder

print("✓ New perception system ready")
```

---

### Phase 2: Parallel Testing (Run Both Systems)

Keep old YOLO system running while testing new VLM system.

**2.1 Test VLM Detection**

```python
from perception_pipeline import IntegratedPerceptionPipeline

pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")

# Test on sample image
result = pipeline.process_image(
    "sample_screenshot.jpg",
    strategy="vlm",  # VLM only first
    save_output=True
)

print(f"VLM found {result['detection']['num_elements']} elements")
```

**2.2 Compare Results**

```python
# Old way (YOLO)
old_detections = pd.read_csv("detected_csvs/sample.csv")
print(f"YOLO found {len(old_detections)} elements")

# New way (VLM)
vlm_elements = result["detection"]["elements"]
print(f"VLM found {len(vlm_elements)} elements")

# Compare
print("\nOld (YOLO):", [d['class_name'] for _, d in old_detections.iterrows()])
print("New (VLM):", [e['type'] for e in vlm_elements])
```

**2.3 Test Hybrid Strategy**

```python
# Now try hybrid (best performance)
result_hybrid = pipeline.process_image(
    "sample_screenshot.jpg",
    strategy="hybrid",  # YOLO + VLM fallback
    save_output=True
)

print(f"Hybrid found {result_hybrid['detection']['num_elements']} elements")
```

---

### Phase 3: Gradual Integration

**3.1 Update Detection Module**

```python
# OLD: src/detection/yolo_detect.py
from ultralytics import YOLO

model = YOLO("best.pt")
results = model.predict(image_path)

# NEW: Still works! But now also supports perception router
# (You don't need to change this file unless you want to)
```

**3.2 Update Interpretation**

Replace game-specific state builder with semantic state builder:

```python
# OLD CODE (still works):
from interpretation.state_builder import build_game_state

game_state = build_game_state(yolo_detections)

# NEW CODE (recommended):
from interpretation.semantic_state_builder import SemanticStateBuilder

builder = SemanticStateBuilder()
semantic_state = builder.build_semantic_state(vlm_elements)
```

**3.3 Add Semantic Queries**

```python
from interpretation.semantic_state_builder import SemanticStateBuilder

builder = SemanticStateBuilder()
state = builder.build_semantic_state(elements)

# Semantic queries (not possible with old YOLO)
clickable = builder.find_clickable_elements(state)
inputs = builder.find_input_elements(state)
login_button = builder.get_element_by_label(state, "Login")
center_elem = builder.get_element_at_position(state, 0.5, 0.5)
```

**3.4 Add Feedback Loop**

```python
from perception import FeedbackLogger

logger = FeedbackLogger()

# Log detection
event_id = logger.log_detection(
    image_path=screenshot_path,
    elements=detected_elements,
    action="click",
    target_element_id="button_id"
)

# Record feedback after action
success = execute_action(...)
logger.mark_feedback(event_id, success=success)

# Get statistics
stats = logger.get_improvement_summary()
```

---

### Phase 4: Full Migration

Update your main pipeline:

```python
# OLD: src/main_capture.py
from capture.ipcam_capture import start_capture

ip = input("Enter phone IP: ")
start_capture(ip)

# NEW: src/main_capture_new.py
from capture.ipcam_capture import start_capture
from perception_pipeline import IntegratedPerceptionPipeline
import cv2
import os

def capture_and_analyze(ip_address):
    """Enhanced capture with perception."""
    
    # Initialize perception pipeline
    pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")
    
    # Start capture
    cap = cv2.VideoCapture(f"http://{ip_address}:8080/video")
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Save frame
        frame_path = f"temp_frame.jpg"
        cv2.imwrite(frame_path, frame)
        
        # Analyze every 5 frames (to save API calls)
        if frame_count % 5 == 0:
            # NEW: Perception analysis
            result = pipeline.process_image(
                frame_path,
                strategy="hybrid"
            )
            
            # Use semantic state
            state = result["semantic_state"]
            
            # Your agent logic here
            actions = agent.reason(state)
            
            # Execute actions
            for action in actions:
                execute_action(action)
            
            # Record feedback
            pipeline.save_feedback(
                result["event_id"],
                success=True
            )
        
        # Display
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
        frame_count += 1
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    ip = input("Enter phone IP: ")
    capture_and_analyze(ip)
```

---

## Migration Checklist

### ✅ Setup Phase
- [ ] Install new dependencies: `pip install -r src/requirements.txt`
- [ ] Set API key: `export ANTHROPIC_API_KEY="..."`
- [ ] Test imports: `from perception import PerceptionRouter`

### ✅ Testing Phase
- [ ] Run on sample image: `perception_pipeline.py --image sample.jpg`
- [ ] Compare VLM vs YOLO vs Hybrid strategies
- [ ] Check annotation quality
- [ ] Verify JSON output format

### ✅ Integration Phase
- [ ] Update interpretation module (use SemanticStateBuilder)
- [ ] Add feedback logging
- [ ] Integrate with agent logic
- [ ] Test end-to-end pipeline

### ✅ Deployment Phase
- [ ] Remove/archive old detection code
- [ ] Update documentation
- [ ] Train team on new system
- [ ] Monitor statistics

---

## Common Migration Issues

### Issue 1: "ANTHROPIC_API_KEY not set"

**Solution:**
```bash
# Make sure to export
export ANTHROPIC_API_KEY="sk-ant-..."

# Or pass in code
router = PerceptionRouter(
    vlm_provider="claude",
    vlm_kwargs={"api_key": "sk-ant-..."}
)
```

### Issue 2: "Old code still uses yolo_detect()"

**Solution:** Keep using it! It's still supported.
```python
# OLD CODE STILL WORKS
from detection.yolo_detect import run_detection
run_detection()  # ✓ Still works

# NEW CODE ALSO WORKS
from perception import PerceptionRouter
router = PerceptionRouter()
result = router.detect()  # ✓ New way
```

### Issue 3: "My interpretation code broke"

**Solution:** Choose what to keep:

```python
# Option 1: Keep using old game-specific state
from interpretation.state_builder import build_game_state
state = build_game_state(yolo_result)  # ✓ Still works

# Option 2: Use new semantic state (recommended)
from interpretation.semantic_state_builder import SemanticStateBuilder
builder = SemanticStateBuilder()
state = builder.build_semantic_state(vlm_elements)  # ✓ More general
```

### Issue 4: "VLM is slower than YOLO"

**Solution:** Use hybrid strategy!

```python
# Fast path for known UIs, VLM fallback for unknown
result = router.detect(
    "image.jpg",
    strategy="hybrid",  # ← Use this!
    yolo_conf=0.6      # Lower threshold to try YOLO more
)
```

### Issue 5: "Can't retrain model for new UI"

**Solution:** That's the point! VLM works zero-shot.

```python
# You don't need to retrain anymore!
result = router.detect(
    "new_ui_screenshot.jpg",
    strategy="vlm"  # Works on ANY UI, no training needed!
)
```

---

## Rollback Plan

If you need to revert to YOLO-only:

```python
# Disable VLM, use YOLO only
router = PerceptionRouter(
    use_vlm=False,      # ← Disable VLM
    use_yolo=True,
    yolo_model_path="best.pt"
)

# Old YOLO code still works
from detection.yolo_detect import run_detection
run_detection()
```

---

## Performance Expectations

### Migration Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Setup | 15 min | Quick |
| Testing | 1-2 hours | Compare strategies |
| Integration | 2-4 hours | Update agent |
| Deployment | 1-2 days | Gradual rollout |

### Cost Analysis

| System | Detection | Feedback | Total/Day |
|--------|-----------|----------|-----------|
| YOLO only | $0 | $0 | $0 |
| VLM only | $1-5 | $0 | $1-5 |
| Hybrid | $0.50-2 | $0 | $0.50-2 |

(Assuming ~100-1000 images/day)

---

## Training & Support

### Resources

1. **Quick Start:** [docs/QUICK_START.md](../docs/QUICK_START.md)
2. **Full Guide:** [docs/PERCEPTION_SYSTEM.md](../docs/PERCEPTION_SYSTEM.md)
3. **Architecture:** [docs/ARCHITECTURE_DIAGRAMS.md](../docs/ARCHITECTURE_DIAGRAMS.md)

### Testing Scenarios

```python
# Test 1: Single image processing
python src/perception_pipeline.py --image test.jpg --provider claude

# Test 2: Batch processing
for img in screenshots/*.jpg:
    python src/perception_pipeline.py --image $img --provider claude

# Test 3: Strategy comparison
# Run with --strategy vlm, --strategy yolo, --strategy hybrid

# Test 4: Integration test
# Run full agent loop with new perception
```

---

## Summary

**Old System (YOLO-only):**
- Fast but limited
- Requires retraining for each app
- Works only on trained UIs

**New System (VLM + YOLO):**
- Generalized, works on any UI
- Zero-shot, no retraining
- Semantic understanding
- Self-improving with feedback
- Backward compatible

**Migration Path:**
1. Install new dependencies
2. Run in parallel for testing
3. Gradually integrate new code
4. Monitor performance
5. Full deployment

**Time to migrate:** 4-8 hours total  
**Benefits:** Future-proof, scalable, extensible

🚀 **Ready to migrate?** Start with [QUICK_START.md](../docs/QUICK_START.md)
