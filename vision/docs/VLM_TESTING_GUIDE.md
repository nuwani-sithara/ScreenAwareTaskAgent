# VLM (Vision Language Model) Testing Guide

## Prerequisites

### 1. API Keys Setup

You need at least ONE of these API keys:

#### Claude (Anthropic) - Recommended
```bash
# Set environment variable
export ANTHROPIC_API_KEY="sk-ant-..."  # On Windows PowerShell:
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Verify
python -c "import os; print('✓' if os.getenv('ANTHROPIC_API_KEY') else '✗ Not set')"
```

Get key from: https://console.anthropic.com/

#### GPT-4V (OpenAI) - Optional
```bash
export OPENAI_API_KEY="sk-..."
```

Get key from: https://platform.openai.com/

#### Local VLM - Optional (No API key needed)
Requires: `pip install transformers torch llava-hf`

### 2. Dependencies
```bash
pip install -r requirements.txt
# Or install individually:
pip install anthropic openai transformers pillow opencv-python
```

### 3. Test Files
- Test images will be created automatically
- Ensure write permissions in `test_output/` directory

---

## Quick Start - Run All Tests

### Option A: Full Automated Test Suite

```bash
cd src
python test_vlm_all_functions.py
```

**Output Example:**
```
======================================================================
  COMPREHENSIVE VLM TESTING SUITE
======================================================================

[INFO] Python: 3.11.4
[INFO] Testing VLM components

[TEST] 1.1 - Check ANTHROPIC_API_KEY... ✓ PASS
        → API Key found: sk-ant-...xyz

[TEST] 2.1 - Create Claude VLM client... ✓ PASS
        → Client type: ClaudeVLMClient

[TEST] 3.1 - Create test image... ✓ PASS
        → Test image created: test_image.jpg

[TEST] 6.1 - Analyze test image with Claude... ✓ PASS
        → Analysis completed in 2.45s
        → Response length: 1523 chars

...

======================================================================
TEST SUMMARY
======================================================================

✓ PASSED: 28
✗ FAILED: 0
⚠ WARNINGS: 2
⊘ SKIPPED: 3
Total Tests: 33

═══════════════════════════════════════
  ✓ ALL TESTS PASSED!
═══════════════════════════════════════
```

---

## Individual Function Tests

### TEST 1: Configuration & API Keys

#### Check API Key Configuration
```bash
python << 'EOF'
import os

print("API Key Status:")
print(f"  ANTHROPIC_API_KEY: {'✓' if os.getenv('ANTHROPIC_API_KEY') else '✗'}")
print(f"  OPENAI_API_KEY: {'✓' if os.getenv('OPENAI_API_KEY') else '✗'}")

# Show masked keys
if os.getenv('ANTHROPIC_API_KEY'):
    key = os.getenv('ANTHROPIC_API_KEY')
    print(f"    → {key[:10]}...{key[-4:]}")
EOF
```

**Expected:**
```
API Key Status:
  ANTHROPIC_API_KEY: ✓
    → sk-ant-...xyz
  OPENAI_API_KEY: ✗
```

---

### TEST 2: VLM Client Factory

#### Get Claude Client
```bash
python << 'EOF'
from perception.vlm.vlm_client import get_vlm_client

client = get_vlm_client('claude')
print(f"Claude client: {type(client).__name__}")
print(f"Available methods: {[m for m in dir(client) if not m.startswith('_')]}")
EOF
```

**Expected:**
```
Claude client: ClaudeVLMClient
Available methods: ['analyze_ui', 'encode_image_to_base64', 'get_image_dimensions']
```

#### Get GPT-4V Client
```bash
python << 'EOF'
from perception.vlm.vlm_client import get_vlm_client

client = get_vlm_client('gpt4v')
if client:
    print(f"✓ GPT-4V client: {type(client).__name__}")
else:
    print("✗ OPENAI_API_KEY not set")
EOF
```

#### Get Local VLM Client
```bash
python << 'EOF'
from perception.vlm.vlm_client import get_vlm_client

try:
    client = get_vlm_client('local')
    print(f"✓ Local client: {type(client).__name__}")
except Exception as e:
    print(f"⚠ Local VLM: {str(e)}")
EOF
```

---

### TEST 3: Image Encoding

#### Encode Image to Base64
```bash
python << 'EOF'
from perception.vlm.vlm_client import get_vlm_client

client = get_vlm_client('claude')

# Test with a real image
image_path = "path/to/your/image.jpg"

encoded = client.encode_image_to_base64(image_path)
print(f"Image encoded: {len(encoded)} bytes")
print(f"First 100 chars: {encoded[:100]}...")
EOF
```

#### Get Image Dimensions
```bash
python << 'EOF'
from perception.vlm.vlm_client import get_vlm_client

client = get_vlm_client('claude')
image_path = "test_image.jpg"

width, height = client.get_image_dimensions(image_path)
print(f"Image dimensions: {width}x{height}")
EOF
```

---

### TEST 4: UI Parser

#### Create UI Element
```bash
python << 'EOF'
from perception.vlm.ui_parser import UIElement

element = UIElement(
    element_id="btn_login",
    element_type="button",
    label="Login",
    bbox=[0.05, 0.08, 0.35, 0.17],
    confidence=0.95
)

print(f"✓ Element created: {element.element_type}")
print(f"  ID: {element.element_id}")
print(f"  Label: {element.label}")
print(f"  Bbox: {element.bbox}")
print(f"  Confidence: {element.confidence}")
EOF
```

**Expected:**
```
✓ Element created: button
  ID: btn_login
  Label: Login
  Bbox: [0.05, 0.08, 0.35, 0.17]
  Confidence: 0.95
```

#### Convert Element to Dict
```bash
python << 'EOF'
from perception.vlm.ui_parser import UIElement
import json

element = UIElement(
    element_id="btn_login",
    element_type="button",
    label="Login",
    bbox=[0.05, 0.08, 0.35, 0.17],
    confidence=0.95
)

element_dict = element.to_dict()
print(json.dumps(element_dict, indent=2))
EOF
```

**Expected:**
```json
{
  "element_id": "btn_login",
  "element_type": "button",
  "label": "Login",
  "bbox": [0.05, 0.08, 0.35, 0.17],
  "confidence": 0.95
}
```

#### Parse UIElement from Dict
```bash
python << 'EOF'
from perception.vlm.ui_parser import UIElement

element_dict = {
    "element_id": "btn_login",
    "element_type": "button",
    "label": "Login",
    "bbox": [0.05, 0.08, 0.35, 0.17],
    "confidence": 0.95
}

element = UIElement.from_dict(element_dict)
print(f"✓ Element restored from dict")
print(f"  Type: {element.element_type}")
print(f"  Label: {element.label}")
EOF
```

#### Normalize Bounding Box
```bash
python << 'EOF'
from perception.vlm.ui_parser import UIParser

parser = UIParser()

# Convert pixel coordinates to normalized (0-1)
# Pixel coords: [50, 50, 250, 100] in 800x600 image
normalized = parser.normalize_bbox(
    bbox=[50, 50, 250, 100],
    image_width=800,
    image_height=600
)

print(f"Original (pixels): [50, 50, 250, 100]")
print(f"Normalized (0-1): {[f'{x:.3f}' for x in normalized]}")
EOF
```

**Expected:**
```
Original (pixels): [50, 50, 250, 100]
Normalized (0-1): ['0.062', '0.083', '0.312', '0.167']
```

#### Normalize Element Type
```bash
python << 'EOF'
from perception.vlm.ui_parser import UIParser

parser = UIParser()

types_to_test = [
    "Button",
    "button",
    "BUTTON",
    "textfield",
    "text_field",
    "Text Field",
    "checkbox",
    "dropdown"
]

for test_type in types_to_test:
    normalized = parser.normalize_element_type(test_type)
    print(f"{test_type:20} → {normalized}")
EOF
```

#### Parse VLM Response
```bash
python << 'EOF'
from perception.vlm.ui_parser import UIParser

parser = UIParser()

# Simulate VLM response
vlm_response = """
The interface contains these elements:
{
    "elements": [
        {
            "id": "btn_1",
            "type": "button",
            "label": "Login",
            "coordinates": {"x1": 50, "y1": 50, "x2": 250, "y2": 100}
        },
        {
            "id": "field_1",
            "type": "textfield",
            "label": "Username",
            "coordinates": {"x1": 50, "y1": 150, "x2": 750, "y2": 200}
        }
    ]
}
"""

elements = parser.parse_vlm_response(
    vlm_response,
    image_width=800,
    image_height=600
)

print(f"✓ Parsed {len(elements)} elements:")
for elem in elements:
    print(f"  - {elem.element_type}: {elem.label}")
EOF
```

---

### TEST 5: Prompt Templates

#### View UI Discovery Prompt
```bash
python << 'EOF'
from perception.vlm.prompt_templates import UI_DISCOVERY_PROMPT

print("UI_DISCOVERY_PROMPT:")
print("=" * 70)
print(UI_DISCOVERY_PROMPT[:500])
print("...")
print(f"Total length: {len(UI_DISCOVERY_PROMPT)} characters")
EOF
```

#### View All Prompts
```bash
python << 'EOF'
from perception.vlm.prompt_templates import (
    UI_DISCOVERY_PROMPT,
    ELEMENT_REFINEMENT_PROMPT,
    SEMANTIC_STATE_PROMPT,
    COMPARISON_PROMPT
)

prompts = {
    'UI_DISCOVERY': UI_DISCOVERY_PROMPT,
    'ELEMENT_REFINEMENT': ELEMENT_REFINEMENT_PROMPT,
    'SEMANTIC_STATE': SEMANTIC_STATE_PROMPT,
    'COMPARISON': COMPARISON_PROMPT
}

for name, prompt in prompts.items():
    print(f"{name:20} → {len(prompt):5} chars")
EOF
```

---

### TEST 6: Claude Live Analysis

#### Analyze Real Image with Claude

**Step 1: Create Test Image**
```bash
python << 'EOF'
import cv2
import numpy as np

# Create a simple UI-like image
img = np.ones((600, 800, 3), dtype=np.uint8) * 255

# Draw button
cv2.rectangle(img, (50, 50), (250, 100), (0, 0, 0), 2)
cv2.putText(img, "Login", (90, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

# Draw text field
cv2.rectangle(img, (50, 150), (750, 200), (0, 0, 0), 2)
cv2.putText(img, "Username", (60, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

# Draw another text field
cv2.rectangle(img, (50, 250), (750, 300), (0, 0, 0), 2)
cv2.putText(img, "Password", (60, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

# Draw submit button
cv2.rectangle(img, (500, 400), (750, 450), (200, 200, 200), -1)
cv2.putText(img, "Submit", (560, 430), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

cv2.imwrite("test_image.jpg", img)
print("✓ Test image created: test_image.jpg")
EOF
```

**Step 2: Analyze with Claude**
```bash
python << 'EOF'
from perception.vlm.vlm_client import get_vlm_client
from perception.vlm.prompt_templates import UI_DISCOVERY_PROMPT
import time

client = get_vlm_client('claude')

print("Analyzing image with Claude...")
start_time = time.time()

response = client.analyze_ui(
    image_path="test_image.jpg",
    prompt=UI_DISCOVERY_PROMPT,
    max_tokens=2000
)

elapsed = time.time() - start_time

print(f"\n✓ Analysis completed in {elapsed:.2f} seconds\n")
print("Claude Response:")
print("=" * 70)
print(response)
EOF
```

**Step 3: Parse Response to Elements**
```bash
python << 'EOF'
from perception.vlm.vlm_client import get_vlm_client
from perception.vlm.ui_parser import UIParser
from perception.vlm.prompt_templates import UI_DISCOVERY_PROMPT

client = get_vlm_client('claude')
parser = UIParser()

# Get analysis
response = client.analyze_ui(
    image_path="test_image.jpg",
    prompt=UI_DISCOVERY_PROMPT,
    max_tokens=2000
)

# Parse to elements
elements = parser.parse_vlm_response(
    response,
    image_width=800,
    image_height=600
)

print(f"✓ Detected {len(elements)} UI elements:\n")

for i, elem in enumerate(elements, 1):
    print(f"{i}. {elem.element_type.upper()}")
    print(f"   Label: {elem.label}")
    print(f"   ID: {elem.element_id}")
    print(f"   Bbox: {elem.bbox}")
    print(f"   Confidence: {elem.confidence}")
    print()
EOF
```

---

### TEST 7: Perception Router

#### Initialize Router
```bash
python << 'EOF'
from perception.perception_router import PerceptionRouter

router = PerceptionRouter(vlm_provider='claude')
print("✓ PerceptionRouter initialized")
print(f"  VLM Provider: {router.vlm_provider}")
EOF
```

#### Detect Elements with VLM
```bash
python << 'EOF'
from perception.perception_router import PerceptionRouter
import json

router = PerceptionRouter(vlm_provider='claude')

result = router.detect(
    image_path="test_image.jpg",
    strategy='vlm'  # 'vlm', 'yolo', 'hybrid'
)

if result['success']:
    print(f"✓ Detection successful")
    print(f"  Elements: {len(result['elements'])}")
    print(f"  Time: {result.get('detection_time', 'N/A')}s")
    
    print("\nElements:")
    for elem in result['elements'][:3]:
        print(f"  - {elem.get('element_type')}: {elem.get('label')}")
else:
    print(f"✗ Detection failed: {result['error']}")
EOF
```

#### Compare Two Images
```bash
python << 'EOF'
from perception.perception_router import PerceptionRouter

router = PerceptionRouter(vlm_provider='claude')

changes = router.detect_changes(
    image1_path="test_image_1.jpg",
    image2_path="test_image_2.jpg"
)

if changes['success']:
    print(f"✓ Comparison completed")
    print(f"  Added elements: {len(changes.get('added', []))}")
    print(f"  Removed elements: {len(changes.get('removed', []))}")
    print(f"  Changed elements: {len(changes.get('changed', []))}")
else:
    print(f"⚠ Comparison failed: {changes.get('error')}")
EOF
```

---

### TEST 8: Full Pipeline Integration

#### Process Image Through Pipeline
```bash
python << 'EOF'
from perception_pipeline import IntegratedPerceptionPipeline
import json

pipeline = IntegratedPerceptionPipeline(vlm_provider='claude')

result = pipeline.process_image(
    image_path="test_image.jpg",
    strategy='vlm',
    save_output=True
)

if result['success']:
    print("✓ Pipeline processing completed")
    print(f"  Elements detected: {result['detection']['num_elements']}")
    print(f"  Analysis time: {result['detection']['analysis_time']:.2f}s")
    print(f"  Output files:")
    for file in result.get('output_files', []):
        print(f"    - {file}")
else:
    print(f"✗ Processing failed: {result['error']}")
EOF
```

#### Get Statistics
```bash
python << 'EOF'
from perception_pipeline import IntegratedPerceptionPipeline

pipeline = IntegratedPerceptionPipeline(vlm_provider='claude')

stats = pipeline.get_statistics()

print("Pipeline Statistics:")
print(f"  Total images processed: {stats.get('total_images', 0)}")
print(f"  Total elements detected: {stats.get('total_elements', 0)}")
print(f"  Average elements per image: {stats.get('avg_elements_per_image', 0):.1f}")
print(f"  Average analysis time: {stats.get('avg_analysis_time', 0):.2f}s")
EOF
```

---

## Advanced Testing

### Test with Your Own Images

```bash
python << 'EOF'
from perception_pipeline import IntegratedPerceptionPipeline

pipeline = IntegratedPerceptionPipeline(vlm_provider='claude')

# Process your image
result = pipeline.process_image(
    image_path="path/to/your/screenshot.png",
    strategy='vlm',
    save_output=True
)

if result['success']:
    print(f"✓ Analyzed: {len(result['detection']['elements'])} elements")
else:
    print(f"✗ Error: {result['error']}")
EOF
```

### Compare Different Strategies

```bash
python << 'EOF'
from perception.perception_router import PerceptionRouter
import time

router = PerceptionRouter(vlm_provider='claude')

strategies = ['vlm', 'yolo', 'hybrid']
results = {}

for strategy in strategies:
    try:
        start = time.time()
        result = router.detect("test_image.jpg", strategy=strategy)
        elapsed = time.time() - start
        
        if result['success']:
            results[strategy] = {
                'elements': len(result['elements']),
                'time': elapsed
            }
        else:
            results[strategy] = {'error': result['error']}
    except Exception as e:
        results[strategy] = {'error': str(e)}

# Print comparison
print("Strategy Comparison:")
print("─" * 50)
for strategy, data in results.items():
    if 'error' in data:
        print(f"{strategy:10} ✗ {data['error']}")
    else:
        print(f"{strategy:10} ✓ {data['elements']:3} elements ({data['time']:.2f}s)")
EOF
```

### Benchmark Performance

```bash
python << 'EOF'
from perception.perception_router import PerceptionRouter
import time

router = PerceptionRouter(vlm_provider='claude')

print("Running performance benchmark...")
print("─" * 50)

times = []
for i in range(5):
    start = time.time()
    result = router.detect("test_image.jpg", strategy='vlm')
    elapsed = time.time() - start
    times.append(elapsed)
    print(f"Run {i+1}: {elapsed:.2f}s")

print("─" * 50)
print(f"Average: {sum(times)/len(times):.2f}s")
print(f"Min: {min(times):.2f}s")
print(f"Max: {max(times):.2f}s")
EOF
```

---

## Troubleshooting

### Issue: "ANTHROPIC_API_KEY not set"

**Solution:**
```bash
# Check if set
echo $ANTHROPIC_API_KEY

# Set it (one-time)
export ANTHROPIC_API_KEY="sk-ant-..."

# Or set permanently (add to ~/.bashrc or ~/.zshrc)
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
```

### Issue: "API Rate Limit Exceeded"

**Solution:**
```bash
# Wait before retrying
import time
time.sleep(60)

# Or use local VLM instead
from perception.vlm.vlm_client import get_vlm_client
client = get_vlm_client('local')
```

### Issue: "Image not found"

**Solution:**
```bash
import os
image_path = "test_image.jpg"

if not os.path.exists(image_path):
    print(f"Error: {image_path} not found")
    print(f"Current directory: {os.getcwd()}")
    print(f"Available files: {os.listdir()}")
```

### Issue: "Claude response format invalid"

**Solution:**
```bash
# Check what Claude returned
response = client.analyze_ui("test_image.jpg", UI_DISCOVERY_PROMPT)
print("Raw response:")
print(response)

# Try parsing with error handling
from perception.vlm.ui_parser import UIParser
parser = UIParser()
elements = parser.parse_vlm_response(response)
print(f"Parsed: {len(elements)} elements")
```

---

## Test Checklist

### Basic Setup
- [ ] ANTHROPIC_API_KEY set
- [ ] `pip install -r requirements.txt` completed
- [ ] Can import VLM modules

### Core Functions
- [ ] Can create Claude client
- [ ] Can encode image to base64
- [ ] Can create UIElement
- [ ] Can parse JSON response

### Live API Tests (requires running)
- [ ] Claude analyzes test image
- [ ] Response parsed to elements
- [ ] Perception router detects elements
- [ ] Pipeline processes image

### Performance
- [ ] API response < 5 seconds
- [ ] JSON parsing < 100ms
- [ ] Full pipeline < 10 seconds

### Error Handling
- [ ] Invalid image path handled
- [ ] Empty response handled
- [ ] Malformed JSON handled
- [ ] Out-of-range bbox handled

---

## Next Steps

1. **Run tests:** `python test_vlm_all_functions.py`
2. **Check output:** Review detection results
3. **Fine-tune:** Adjust confidence thresholds if needed
4. **Deploy:** Integrate with your agent code

Good luck! 🚀

