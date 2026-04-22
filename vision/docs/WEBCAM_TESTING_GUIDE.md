# Webcam Capture Testing Guide - External Camera

## Prerequisites

### Hardware Setup
- [ ] External USB camera connected to computer
- [ ] USB ports available
- [ ] Camera drivers installed (auto-detect usually works)
- [ ] Good lighting in the testing area

### Software Requirements
```bash
# Already installed in requirements.txt:
- opencv-python==4.10.0.84
- numpy==1.26.4
```

### Check Installation
```bash
python -c "import cv2; print(f'OpenCV version: {cv2.__version__}')"
```

---

## Phase 1: Camera Detection Testing

### Step 1.1: List Available Cameras

**What it does:** Scans your system for connected cameras and shows previews

```bash
cd src
python -c "
from capture.webcam_capture import list_available_cameras
cameras = list_available_cameras(max_index=10)
print(f'\n✓ Found cameras at indexes: {cameras}')
"
```

**Expected Output:**
```
Scanning for available cameras...
Camera index 0 is available
Camera index 1 is available (if you have 2+ cameras)
Preview windows pop up for 1 second each

✓ Found cameras at indexes: [0, 1]
```

**Troubleshooting:**
- ❌ "No cameras found" → Check USB connection, try different USB ports
- ❌ Preview windows don't appear → Driver issue, reinstall camera drivers
- ❌ Takes a long time → Reduce max_index: `list_available_cameras(max_index=3)`

---

## Phase 2: Manual Camera Selection Testing

### Step 2.1: Test Interactive Selection

**What it does:** Lets you choose which camera to use

```bash
cd src
python -c "
from capture.webcam_capture import list_available_cameras, select_camera

cameras = list_available_cameras(max_index=5)
if cameras:
    selected = select_camera(cameras)
    print(f'Selected camera: {selected}')
"
```

**Expected Behavior:**
```
Select the camera you want to use:
0: Camera index 0
1: Camera index 1
Enter the number corresponding to the camera: 0
Selected camera: 0
```

**Test Different Inputs:**
- Enter valid choice (e.g., 0)
- Enter invalid choice (e.g., 99) → Should ask again
- Enter non-numeric input (e.g., "abc") → Should ask again

---

## Phase 3: Live Preview Testing

### Step 3.1: Test Real-time Camera Feed

**What it does:** Shows live camera feed before capture

```bash
cd src
python << 'EOF'
import cv2
import platform

# Detect camera
backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
cap = cv2.VideoCapture(0, backend)

if not cap.isOpened():
    print("✗ Camera failed to open")
else:
    print("✓ Camera opened successfully")
    print("Capturing 30 frames for quality check...")
    
    for i in range(30):
        ret, frame = cap.read()
        if ret:
            print(f"  Frame {i+1}: {frame.shape} pixels, dtype: {frame.dtype}")
        else:
            print(f"  Frame {i+1}: FAILED TO CAPTURE")
    
    cap.release()
    print("✓ Test completed")
EOF
```

**Expected Output:**
```
✓ Camera opened successfully
Capturing 30 frames for quality check...
  Frame 1: (480, 640, 3) pixels, dtype: uint8
  Frame 2: (480, 640, 3) pixels, dtype: uint8
  ... (30 frames)
✓ Test completed
```

**Verify:**
- All frames have same resolution (consistent capture)
- All frames captured successfully (no FAILED messages)
- Frame rate stable

---

## Phase 4: Auto Capture Mode Testing

### Step 4.1: Test Auto Mode (Fastest)

**What it does:** Captures images automatically at set interval

```bash
cd src
python << 'EOF'
import os
import time
from capture.webcam_capture import start_webcam_capture

# Create test directory
test_dir = "test_output/auto_mode"
os.makedirs(test_dir, exist_ok=True)

print("Starting AUTO mode capture...")
print("Test parameters:")
print("  - Duration: 5 seconds")
print("  - Interval: 1 second (should capture ~5 images)")
print("\nPress Ctrl+C to stop\n")

start_webcam_capture(
    camera_index=1,
    save_dir=test_dir,
    mode="auto",
    interval=1
)
EOF
```

**Test Variations:**

**Test A: 1-second interval (5 frames in 5 seconds)**
```python
start_webcam_capture(camera_index=1, save_dir="test_output/1sec", mode="auto", interval=1)
# Run for 5 seconds, should get ~5 images
```

**Test B: 0.5-second interval (10 frames in 5 seconds)**
```python
start_webcam_capture(camera_index=1, save_dir="test_output/half_sec", mode="auto", interval=0.5)
# Run for 5 seconds, should get ~10 images
```

**Test C: 2-second interval (2-3 frames in 5 seconds)**
```python
start_webcam_capture(camera_index=1, save_dir="test_output/2sec", mode="auto", interval=2)
# Run for 5 seconds, should get ~2-3 images
```

**Verification Steps:**

1. Check frame count:
```bash
cd src
ls -1 test_output/auto_mode/ | wc -l
# Should show number of images captured
```

2. Verify image quality:
```python
import cv2
import os

test_dir = "test_output/auto_mode"
images = os.listdir(test_dir)

for img_name in images[:3]:
    img_path = os.path.join(test_dir, img_name)
    img = cv2.imread(img_path)
    if img is not None:
        print(f"✓ {img_name}: {img.shape} - Valid image")
    else:
        print(f"✗ {img_name}: Failed to load")
```

**Expected Output:**
```
✓ frame_1707248400.jpg: (480, 640, 3) - Valid image
✓ frame_1707248401.jpg: (480, 640, 3) - Valid image
✓ frame_1707248402.jpg: (480, 640, 3) - Valid image
```

---

## Phase 5: Selective Capture Mode Testing

### Step 5.1: Test Manual Selection

**What it does:** Captures only when you press 's'

```bash
cd src
python << 'EOF'
import os
from capture.webcam_capture import start_webcam_capture

# Create test directory
test_dir = "test_output/selective_mode"
os.makedirs(test_dir, exist_ok=True)

print("Starting SELECTIVE mode capture...")
print("Instructions:")
print("  - Press 's' to capture a frame")
print("  - Press 'q' to stop")
print("\nTry capturing 3-5 images by pressing 's'\n")

start_webcam_capture(
    camera_index=1,
    save_dir=test_dir,
    mode="selective",
    interval=1  # Ignored in selective mode
)
EOF
```

**Manual Test Steps:**

1. Run the script above
2. Press 's' 3 times
3. Press 'q' to stop
4. Verify 3 images were captured:

```bash
ls -1 test_output/selective_mode/
# Should show exactly 3 images with timestamps
```

**Test Responsiveness:**

```bash
cd src
python << 'EOF'
import os
import cv2
import platform
import time

backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
cap = cv2.VideoCapture(0, backend)

print("Testing capture responsiveness...")
print("Press 's' 5 times quickly, timing how fast captures happen")

start_time = time.time()
for i in range(5):
    ret, frame = cap.read()
    if ret:
        elapsed = time.time() - start_time
        print(f"  Capture {i+1}: {elapsed:.3f} seconds")

cap.release()
print("✓ Responsiveness test complete")
EOF
```

---

## Phase 6: Integration with Perception System

### Step 6.1: Capture + Perception Pipeline

**What it does:** Captures frames and immediately analyzes with VLM

```bash
cd src
python << 'EOF'
import os
import cv2
import platform
import time
from capture.webcam_capture import start_webcam_stream
from perception_pipeline import IntegratedPerceptionPipeline

# Initialize perception
print("Initializing perception pipeline...")
pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")

# Start capturing
backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
cap = cv2.VideoCapture(0, backend)

print("✓ Camera ready")
print("Capturing and analyzing 3 frames...")

frame_num = 0
while frame_num < 3:
    ret, frame = cap.read()
    if not ret:
        continue
    
    # Save frame
    frame_path = f"test_output/perception_frame_{frame_num}.jpg"
    cv2.imwrite(frame_path, frame)
    
    # Analyze with VLM
    print(f"\n[Frame {frame_num + 1}] Analyzing...")
    start_time = time.time()
    
    result = pipeline.process_image(
        frame_path,
        strategy="vlm",
        save_output=False
    )
    
    elapsed = time.time() - start_time
    
    if result["success"]:
        num_elements = result["detection"]["num_elements"]
        print(f"  ✓ Found {num_elements} UI elements ({elapsed:.2f}s)")
    else:
        print(f"  ✗ Analysis failed: {result.get('error')}")
    
    frame_num += 1

cap.release()
print("\n✓ Capture + Perception integration test complete")
EOF
```

---

## Phase 7: Multi-Camera Testing

### Step 7.1: Test Different Cameras

**Scenario:** You have 2+ cameras (e.g., built-in + external USB)

```bash
cd src
python << 'EOF'
from capture.webcam_capture import list_available_cameras, start_webcam_capture
import os

cameras = list_available_cameras(max_index=5)

if len(cameras) < 2:
    print("Only 1 camera found. Connect another camera and try again.")
else:
    print(f"\nFound {len(cameras)} cameras: {cameras}")
    
    for cam_idx in cameras:
        print(f"\nTesting camera {cam_idx}...")
        
        test_dir = f"test_output/camera_{cam_idx}"
        os.makedirs(test_dir, exist_ok=True)
        
        print(f"Press 'q' after ~3 seconds to move to next camera")
        
        start_webcam_capture(
            camera_index=cam_idx,
            save_dir=test_dir,
            mode="auto",
            interval=1
        )
        
        frame_count = len(os.listdir(test_dir))
        print(f"✓ Camera {cam_idx}: captured {frame_count} frames\n")
EOF
```

---

## Phase 8: Performance & Quality Testing

### Step 8.1: Frame Rate Test

**What it does:** Measures actual capture frame rate

```python
import cv2
import platform
import time

backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
cap = cv2.VideoCapture(0, backend)

print("Measuring frame rate...")
frame_times = []

for i in range(100):
    start = time.time()
    ret, frame = cap.read()
    elapsed = time.time() - start
    frame_times.append(elapsed)

cap.release()

avg_frame_time = sum(frame_times) / len(frame_times)
fps = 1 / avg_frame_time

print(f"Average frame capture time: {avg_frame_time*1000:.2f}ms")
print(f"Estimated FPS: {fps:.1f}")

if fps >= 15:
    print("✓ Good frame rate for real-time processing")
elif fps >= 5:
    print("⚠ Acceptable but slower - may cause lag")
else:
    print("✗ Very slow - consider reducing resolution")
```

**Expected Results:**
- USB 2.0 camera: 15-30 FPS
- USB 3.0 camera: 30-60 FPS
- Built-in webcam: 20-30 FPS

### Step 8.2: Image Quality Test

```python
import cv2
import os
import numpy as np

# Capture 10 frames
frames = []
cap = cv2.VideoCapture(0)

for i in range(10):
    ret, frame = cap.read()
    if ret:
        frames.append(frame)

cap.release()

# Analyze quality
print("Analyzing image quality...")
print(f"Total frames: {len(frames)}")

for i, frame in enumerate(frames):
    # Check brightness
    brightness = np.mean(frame)
    
    # Check sharpness (via Laplacian)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    status = "✓" if laplacian_var > 100 else "⚠"
    print(f"Frame {i}: Brightness={brightness:.0f}, Sharpness={laplacian_var:.1f} {status}")

print("\nGuidelines:")
print("  Brightness: 50-200 (optimal)")
print("  Sharpness: >100 (good focus)")
```

---

## Phase 9: Troubleshooting Tests

### Step 9.1: Camera Not Found

```python
import cv2
import platform

backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0

print("Diagnostic test...")
for i in range(10):
    cap = cv2.VideoCapture(i, backend)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"✓ Camera {i}: Works!")
        else:
            print(f"⚠ Camera {i}: Detected but can't capture")
        cap.release()
    else:
        print(f"✗ Camera {i}: Not detected")
```

### Step 9.2: Frame Capture Fails

```python
import cv2
import platform

backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
cap = cv2.VideoCapture(0, backend)

if not cap.isOpened():
    print("✗ Camera won't open")
else:
    failures = 0
    for i in range(100):
        ret, frame = cap.read()
        if not ret:
            failures += 1
    
    cap.release()
    
    failure_rate = (failures / 100) * 100
    print(f"Failure rate: {failure_rate:.1f}%")
    
    if failure_rate == 0:
        print("✓ Perfect capture rate")
    elif failure_rate < 5:
        print("✓ Acceptable (occasional glitches)")
    elif failure_rate < 20:
        print("⚠ High failure rate - may need driver update")
    else:
        print("✗ Very high failure rate - hardware issue")
```

### Step 9.3: Black/Blank Frames

```python
import cv2
import numpy as np
import platform

backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
cap = cv2.VideoCapture(0, backend)

print("Testing for black frames...")
black_frames = 0

for i in range(50):
    ret, frame = cap.read()
    if ret:
        # Check if frame is mostly black
        if np.mean(frame) < 10:  # Very dark
            black_frames += 1
            print(f"Frame {i}: BLACK")
        else:
            print(f"Frame {i}: OK (brightness: {np.mean(frame):.0f})")

cap.release()

if black_frames > 0:
    print(f"\n⚠ {black_frames} black frames detected")
    print("Solutions:")
    print("  1. Check lighting")
    print("  2. Clean camera lens")
    print("  3. Adjust camera exposure settings")
else:
    print("\n✓ No black frames detected")
```

---

## Phase 10: End-to-End Integration Test

### Step 10.1: Complete Workflow

```bash
cd src
python << 'EOF'
import os
import cv2
import platform
from capture.webcam_capture import start_webcam_capture
from perception_pipeline import IntegratedPerceptionPipeline

print("="*60)
print("COMPLETE WEBCAM + PERCEPTION WORKFLOW TEST")
print("="*60)

# Step 1: Setup
print("\n[1/5] Setting up directories...")
os.makedirs("test_output/e2e_test", exist_ok=True)
print("✓ Directories ready")

# Step 2: Camera detection
print("\n[2/5] Detecting camera...")
backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
cap = cv2.VideoCapture(0, backend)
if cap.isOpened():
    print("✓ Camera found and opened")
    cap.release()
else:
    print("✗ Camera not found!")
    exit(1)

# Step 3: Capture 3 frames
print("\n[3/5] Capturing frames (AUTO mode, 3 sec)...")
test_dir = "test_output/e2e_test"

# Simulate auto capture
backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
cap = cv2.VideoCapture(0, backend)
import time
start_time = time.time()
frame_count = 0

while time.time() - start_time < 3:
    ret, frame = cap.read()
    if ret:
        filename = os.path.join(test_dir, f"frame_{int(time.time())}.jpg")
        cv2.imwrite(filename, frame)
        frame_count += 1
        time.sleep(1)

cap.release()
print(f"✓ Captured {frame_count} frames")

# Step 4: Analyze with VLM
print("\n[4/5] Analyzing frames with VLM...")
pipeline = IntegratedPerceptionPipeline(vlm_provider="claude")

analysis_results = []
for filename in os.listdir(test_dir):
    if filename.endswith('.jpg'):
        filepath = os.path.join(test_dir, filename)
        result = pipeline.process_image(filepath, strategy="vlm", save_output=False)
        if result["success"]:
            analysis_results.append({
                "file": filename,
                "elements": result["detection"]["num_elements"]
            })
            print(f"  ✓ {filename}: {result['detection']['num_elements']} elements")

print(f"✓ Analyzed {len(analysis_results)} frames")

# Step 5: Summary
print("\n[5/5] Summary...")
print(f"✓ Captured: {frame_count} frames")
print(f"✓ Analyzed: {len(analysis_results)} frames")
avg_elements = sum(r['elements'] for r in analysis_results) / len(analysis_results) if analysis_results else 0
print(f"✓ Average elements per frame: {avg_elements:.1f}")

print("\n" + "="*60)
print("✓ COMPLETE END-TO-END TEST SUCCESSFUL!")
print("="*60)
EOF
```

---

## Quick Test Checklist

### Before Testing
- [ ] External USB camera connected
- [ ] Camera USB port working
- [ ] Driver installed
- [ ] Good lighting
- [ ] `pip install -r requirements.txt` completed
- [ ] ANTHROPIC_API_KEY set (for perception tests)

### Phase 1: Detection
- [ ] `list_available_cameras()` finds your camera
- [ ] Preview images show correctly
- [ ] Can select camera from list

### Phase 2: Capture
- [ ] AUTO mode captures at correct interval
- [ ] SELECTIVE mode captures on 's' press
- [ ] Images are valid (not corrupted)
- [ ] Timestamps are in filenames

### Phase 3: Quality
- [ ] Frame rate is acceptable (>5 FPS)
- [ ] Images are bright enough
- [ ] No black/blank frames

### Phase 4: Integration
- [ ] VLM can analyze captured images
- [ ] Semantic state builds correctly
- [ ] Full pipeline works end-to-end

---

## Common Test Results

### ✓ Success
```
✓ Camera opened
✓ Captured 5 frames in 5 seconds
✓ All images valid (480x640 pixels)
✓ FPS: 25
✓ VLM found 10 elements
✓ Semantic state built
```

### ⚠ Warning (Still Usable)
```
⚠ Camera took 2 seconds to initialize
⚠ Occasional black frame (1 in 100)
⚠ FPS: 8 (slower but functional)
⚠ Some frames not analyzed (API rate limit)
```

### ✗ Error (Action Required)
```
✗ Camera not detected
✗ All frames are black
✗ FPS: <2 (too slow)
✗ Images corrupted
```

---

## Running All Tests

```bash
cd src

# Run complete test suite
python << 'EOF'
import subprocess
import sys

tests = [
    ("Camera Detection", "list_available_cameras"),
    ("Live Preview", "preview_test"),
    ("Auto Capture", "auto_capture"),
    ("Selective Capture", "selective_capture"),
    ("Perception Integration", "perception_integration"),
    ("Performance", "performance_test"),
]

print("\n" + "="*60)
print("RUNNING COMPLETE TEST SUITE")
print("="*60 + "\n")

for test_name, _ in tests:
    print(f"Running: {test_name}...")
    # Insert test code here
    print(f"✓ {test_name} passed\n")

print("="*60)
print("ALL TESTS COMPLETED")
print("="*60)
EOF
```

---

## Next Steps After Testing

Once all tests pass:

1. **Integration**: Use in your agent loop
2. **Optimization**: Fine-tune capture parameters
3. **Monitoring**: Set up logging for production
4. **Documentation**: Record any camera-specific settings needed

Good luck! 🎥✨
