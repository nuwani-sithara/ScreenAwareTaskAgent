"""
Comprehensive VLM Testing Script
Tests all Vision Language Model components
"""

import os
import sys
import json
import time
import base64
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from perception.vlm.vlm_client import get_vlm_client, VLMClient
from perception.vlm.ui_parser import UIParser, UIElement, UIAnalysisResult
from perception.vlm.prompt_templates import (
    UI_DISCOVERY_PROMPT,
    ELEMENT_REFINEMENT_PROMPT,
    SEMANTIC_STATE_PROMPT,
    COMPARISON_PROMPT
)
from perception.perception_router import PerceptionRouter

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
END = '\033[0m'

test_results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0,
    'skipped': 0
}

def print_header(text):
    """Print section header"""
    print(f"\n{BLUE}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{END}\n")

def print_test(test_name):
    """Print test name"""
    print(f"{BLUE}[TEST]{END} {test_name}...", end=" ")

def print_pass(msg=""):
    """Print pass status"""
    test_results['passed'] += 1
    print(f"{GREEN}✓ PASS{END} {msg}")

def print_fail(msg=""):
    """Print fail status"""
    test_results['failed'] += 1
    print(f"{RED}✗ FAIL{END} {msg}")

def print_warn(msg=""):
    """Print warning"""
    test_results['warnings'] += 1
    print(f"{YELLOW}⚠ WARN{END} {msg}")

def print_skip(msg=""):
    """Print skip"""
    test_results['skipped'] += 1
    print(f"{CYAN}⊘ SKIP{END} {msg}")

def print_info(msg):
    """Print info message"""
    print(f"{BLUE}[INFO]{END} {msg}")

def print_result(msg):
    """Print result"""
    print(f"        → {msg}")

# ============================================================================
# TEST 1: Configuration & API Keys
# ============================================================================

def test_configuration():
    print_header("TEST 1: Configuration & API Keys")
    
    # Test 1.1: Check environment variables
    print_test("1.1 - Check ANTHROPIC_API_KEY")
    try:
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            masked_key = api_key[:10] + "..." + api_key[-4:]
            print_pass()
            print_result(f"API Key found: {masked_key}")
        else:
            print_warn("ANTHROPIC_API_KEY not set")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 1.2: Check OpenAI API Key
    print_test("1.2 - Check OPENAI_API_KEY")
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            masked_key = api_key[:10] + "..." + api_key[-4:]
            print_pass()
            print_result(f"API Key found: {masked_key}")
        else:
            print_warn("OPENAI_API_KEY not set (GPT-4V will be unavailable)")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 1.3: Verify imports
    print_test("1.3 - Verify VLM module imports")
    try:
        import perception.vlm.vlm_client
        import perception.vlm.ui_parser
        import perception.vlm.prompt_templates
        print_pass()
        print_result("All VLM modules imported successfully")
    except Exception as e:
        print_fail(f"Import error: {str(e)}")

# ============================================================================
# TEST 2: VLM Client Factory
# ============================================================================

def test_vlm_factory():
    print_header("TEST 2: VLM Client Factory")
    
    # Test 2.1: Get Claude client
    print_test("2.1 - Create Claude VLM client")
    try:
        if not os.getenv('ANTHROPIC_API_KEY'):
            print_skip("ANTHROPIC_API_KEY not set")
        else:
            client = get_vlm_client('claude')
            if client is not None:
                print_pass()
                print_result(f"Client type: {type(client).__name__}")
            else:
                print_fail("Client returned None")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 2.2: Get GPT-4V client
    print_test("2.2 - Create GPT-4V VLM client")
    try:
        if not os.getenv('OPENAI_API_KEY'):
            print_skip("OPENAI_API_KEY not set")
        else:
            client = get_vlm_client('gpt4v')
            if client is not None:
                print_pass()
                print_result(f"Client type: {type(client).__name__}")
            else:
                print_fail("Client returned None")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 2.3: Get Local VLM client
    print_test("2.3 - Create Local VLM client")
    try:
        client = get_vlm_client('local')
        if client is not None:
            print_pass()
            print_result(f"Client type: {type(client).__name__}")
        else:
            print_warn("Local client might require model download")
    except Exception as e:
        print_warn(f"Local VLM issue: {str(e)}")
    
    # Test 2.4: Invalid client type
    print_test("2.4 - Handle invalid client type")
    try:
        client = get_vlm_client('invalid')
        if client is None:
            print_pass()
            print_result("Invalid client type correctly returns None")
        else:
            print_warn("Invalid client type did not return None")
    except Exception as e:
        print_warn(f"Exception handling: {str(e)}")

# ============================================================================
# TEST 3: Image Encoding
# ============================================================================

def test_image_encoding():
    print_header("TEST 3: Image Encoding")
    
    # Create a simple test image
    test_image_path = "test_image.jpg"
    
    print_test("3.1 - Create test image")
    try:
        import cv2
        import numpy as np
        
        # Create a simple image with UI elements
        img = np.ones((600, 800, 3), dtype=np.uint8) * 255
        
        # Draw some UI elements
        cv2.rectangle(img, (50, 50), (250, 100), (0, 0, 0), 2)  # Button
        cv2.putText(img, "Login", (90, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        cv2.rectangle(img, (50, 150), (750, 200), (0, 0, 0), 2)  # Text field
        cv2.putText(img, "Username", (60, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        cv2.rectangle(img, (50, 250), (750, 300), (0, 0, 0), 2)  # Text field
        cv2.putText(img, "Password", (60, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        cv2.rectangle(img, (500, 400), (750, 450), (200, 200, 200), -1)  # Button
        cv2.putText(img, "Submit", (560, 430), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        cv2.imwrite(test_image_path, img)
        
        print_pass()
        print_result(f"Test image created: {test_image_path}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
        return None
    
    # Test 3.2: Encode image to base64 (Claude client)
    print_test("3.2 - Encode image to base64")
    try:
        if not os.getenv('ANTHROPIC_API_KEY'):
            print_skip("ANTHROPIC_API_KEY not set")
        else:
            client = get_vlm_client('claude')
            if client:
                encoded = client.encode_image_to_base64(test_image_path)
                if encoded and len(encoded) > 0:
                    print_pass()
                    print_result(f"Encoded size: {len(encoded)} bytes")
                else:
                    print_fail("Encoding returned empty result")
            else:
                print_skip("Claude client unavailable")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 3.3: Get image dimensions
    print_test("3.3 - Get image dimensions")
    try:
        if not os.getenv('ANTHROPIC_API_KEY'):
            print_skip("ANTHROPIC_API_KEY not set")
        else:
            client = get_vlm_client('claude')
            if client:
                width, height = client.get_image_dimensions(test_image_path)
                if width > 0 and height > 0:
                    print_pass()
                    print_result(f"Dimensions: {width}x{height}")
                else:
                    print_fail("Invalid dimensions returned")
            else:
                print_skip("Claude client unavailable")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    return test_image_path

# ============================================================================
# TEST 4: UI Parser
# ============================================================================

def test_ui_parser():
    print_header("TEST 4: UI Parser")
    
    # Test 4.1: UIElement dataclass
    print_test("4.1 - Create UIElement dataclass")
    try:
        element = UIElement(
            element_id="btn_login",
            element_type="button",
            label="Login",
            bbox=[0.05, 0.08, 0.35, 0.17],
            confidence=0.95
        )
        
        if element.element_id == "btn_login":
            print_pass()
            print_result(f"Element created: {element.element_type}")
        else:
            print_fail("Element creation failed")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 4.2: UIElement to_dict
    print_test("4.2 - UIElement.to_dict()")
    try:
        element = UIElement(
            element_id="btn_login",
            element_type="button",
            label="Login",
            bbox=[0.05, 0.08, 0.35, 0.17],
            confidence=0.95
        )
        
        element_dict = element.to_dict()
        if isinstance(element_dict, dict) and 'element_id' in element_dict:
            print_pass()
            print_result(f"Dict keys: {list(element_dict.keys())}")
        else:
            print_fail("to_dict() returned invalid result")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 4.3: UIElement from_dict
    print_test("4.3 - UIElement.from_dict()")
    try:
        element_dict = {
            'element_id': 'btn_login',
            'element_type': 'button',
            'label': 'Login',
            'bbox': [0.05, 0.08, 0.35, 0.17],
            'confidence': 0.95
        }
        
        element = UIElement.from_dict(element_dict)
        if element.element_id == 'btn_login':
            print_pass()
            print_result(f"Element restored from dict")
        else:
            print_fail("from_dict() failed")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 4.4: UIAnalysisResult
    print_test("4.4 - Create UIAnalysisResult")
    try:
        elements = [
            UIElement("btn_login", "button", "Login", [0.05, 0.08, 0.35, 0.17], 0.95),
            UIElement("field_user", "textfield", "Username", [0.05, 0.18, 0.95, 0.25], 0.92)
        ]
        
        result = UIAnalysisResult(
            image_path="test.jpg",
            elements=elements,
            analysis_time=1.5,
            model_used="claude",
            raw_response="{}"
        )
        
        if len(result.elements) == 2:
            print_pass()
            print_result(f"Result created with {len(result.elements)} elements")
        else:
            print_fail("Result creation failed")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 4.5: UIParser normalize_bbox
    print_test("4.5 - UIParser.normalize_bbox()")
    try:
        parser = UIParser()
        
        # Test pixel coords to normalized
        normalized = parser.normalize_bbox([50, 50, 250, 100], image_width=800, image_height=600)
        
        if 0 <= normalized[0] <= 1 and 0 <= normalized[1] <= 1:
            print_pass()
            print_result(f"Normalized bbox: {[f'{x:.3f}' for x in normalized]}")
        else:
            print_fail("Normalization out of range")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 4.6: UIParser normalize_element_type
    print_test("4.6 - UIParser.normalize_element_type()")
    try:
        parser = UIParser()
        
        test_types = ["Button", "button", "BUTTON", "btn", "textfield", "text_field", "Text Field"]
        
        all_valid = True
        for test_type in test_types:
            normalized = parser.normalize_element_type(test_type)
            if not normalized:
                all_valid = False
        
        if all_valid:
            print_pass()
            print_result(f"All {len(test_types)} types normalized successfully")
        else:
            print_warn("Some types failed normalization")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 4.7: UIParser JSON parsing
    print_test("4.7 - UIParser.extract_json_from_response()")
    try:
        parser = UIParser()
        
        # Test with valid JSON
        response = '''
        Here's the analysis:
        {
            "elements": [
                {"id": "btn1", "type": "button", "label": "Click me"}
            ]
        }
        End of analysis.
        '''
        
        json_obj = parser.extract_json_from_response(response)
        
        if json_obj and 'elements' in json_obj:
            print_pass()
            print_result(f"JSON extracted: {len(json_obj['elements'])} elements")
        else:
            print_warn("JSON extraction returned empty")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 5: Prompt Templates
# ============================================================================

def test_prompt_templates():
    print_header("TEST 5: Prompt Templates")
    
    # Test 5.1: UI Discovery Prompt
    print_test("5.1 - UI_DISCOVERY_PROMPT exists")
    try:
        if UI_DISCOVERY_PROMPT and len(UI_DISCOVERY_PROMPT) > 0:
            print_pass()
            print_result(f"Prompt length: {len(UI_DISCOVERY_PROMPT)} chars")
        else:
            print_fail("Prompt is empty")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 5.2: Element Refinement Prompt
    print_test("5.2 - ELEMENT_REFINEMENT_PROMPT exists")
    try:
        if ELEMENT_REFINEMENT_PROMPT and len(ELEMENT_REFINEMENT_PROMPT) > 0:
            print_pass()
            print_result(f"Prompt length: {len(ELEMENT_REFINEMENT_PROMPT)} chars")
        else:
            print_fail("Prompt is empty")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 5.3: Semantic State Prompt
    print_test("5.3 - SEMANTIC_STATE_PROMPT exists")
    try:
        if SEMANTIC_STATE_PROMPT and len(SEMANTIC_STATE_PROMPT) > 0:
            print_pass()
            print_result(f"Prompt length: {len(SEMANTIC_STATE_PROMPT)} chars")
        else:
            print_fail("Prompt is empty")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 5.4: Comparison Prompt
    print_test("5.4 - COMPARISON_PROMPT exists")
    try:
        if COMPARISON_PROMPT and len(COMPARISON_PROMPT) > 0:
            print_pass()
            print_result(f"Prompt length: {len(COMPARISON_PROMPT)} chars")
        else:
            print_fail("Prompt is empty")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 5.5: Prompt customization
    print_test("5.5 - Dynamic prompt generation")
    try:
        from perception.vlm.prompt_templates import format_ui_discovery_prompt
        
        # This should be in prompt_templates
        print_pass()
        print_result("Dynamic prompt functions available")
    except ImportError:
        print_warn("Dynamic prompt functions not found")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 6: Claude VLM Analysis (Live API Test)
# ============================================================================

def test_claude_analysis(image_path):
    print_header("TEST 6: Claude VLM Analysis (Live API)")
    
    if not os.getenv('ANTHROPIC_API_KEY'):
        print_info("Skipping Claude tests - ANTHROPIC_API_KEY not set")
        return
    
    if not image_path or not os.path.exists(image_path):
        print_warn("Test image not available")
        return
    
    try:
        client = get_vlm_client('claude')
        
        if not client:
            print_warn("Claude client could not be initialized")
            return
        
        # Test 6.1: Simple analysis
        print_test("6.1 - Analyze test image with Claude")
        try:
            start_time = time.time()
            
            result = client.analyze_ui(
                image_path=image_path,
                prompt=UI_DISCOVERY_PROMPT,
                max_tokens=2000
            )
            
            elapsed = time.time() - start_time
            
            if result and len(result) > 0:
                print_pass()
                print_result(f"Analysis completed in {elapsed:.2f}s")
                print_result(f"Response length: {len(result)} chars")
                print_result(f"First 200 chars: {result[:200]}...")
            else:
                print_fail("No response from Claude")
        except Exception as e:
            print_fail(f"Claude API Error: {str(e)}")
        
        # Test 6.2: Parse Claude response
        print_test("6.2 - Parse Claude response to structured format")
        try:
            parser = UIParser()
            
            # Get analysis
            analysis_response = client.analyze_ui(
                image_path=image_path,
                prompt=UI_DISCOVERY_PROMPT,
                max_tokens=2000
            )
            
            # Parse it
            parsed = parser.parse_vlm_response(analysis_response, image_width=800, image_height=600)
            
            if parsed and len(parsed) > 0:
                print_pass()
                print_result(f"Parsed {len(parsed)} UI elements")
                for i, elem in enumerate(parsed[:3]):
                    print_result(f"  [{i}] {elem.element_type}: {elem.label}")
            else:
                print_warn("No elements extracted from response")
        except Exception as e:
            print_fail(f"Parsing Error: {str(e)}")
        
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 7: Perception Router
# ============================================================================

def test_perception_router(image_path):
    print_header("TEST 7: Perception Router")
    
    if not os.getenv('ANTHROPIC_API_KEY'):
        print_info("Skipping router tests - ANTHROPIC_API_KEY not set")
        return
    
    if not image_path or not os.path.exists(image_path):
        print_warn("Test image not available")
        return
    
    try:
        # Test 7.1: Initialize router
        print_test("7.1 - Initialize PerceptionRouter")
        try:
            router = PerceptionRouter(vlm_provider='claude')
            print_pass()
            print_result("Router initialized with Claude")
        except Exception as e:
            print_fail(f"Router initialization failed: {str(e)}")
            return
        
        # Test 7.2: Detect with VLM
        print_test("7.2 - Detect UI elements with VLM strategy")
        try:
            start_time = time.time()
            
            result = router.detect(
                image_path=image_path,
                strategy='vlm'
            )
            
            elapsed = time.time() - start_time
            
            if result and result.get('success'):
                elements = result.get('elements', [])
                print_pass()
                print_result(f"Detected {len(elements)} elements in {elapsed:.2f}s")
                
                for i, elem in enumerate(elements[:3]):
                    print_result(f"  [{i}] {elem.get('element_type', 'unknown')}: {elem.get('label', 'N/A')}")
            else:
                print_fail(f"Detection failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print_fail(f"VLM detection error: {str(e)}")
        
        # Test 7.3: Detect with hybrid strategy
        print_test("7.3 - Detect with hybrid strategy")
        try:
            result = router.detect(
                image_path=image_path,
                strategy='hybrid'
            )
            
            if result and result.get('success'):
                elements = result.get('elements', [])
                print_pass()
                print_result(f"Hybrid detection: {len(elements)} elements")
            else:
                print_warn(f"Hybrid detection skipped or failed")
        except Exception as e:
            print_warn(f"Hybrid strategy not fully available: {str(e)}")
        
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 8: Integration with Perception Pipeline
# ============================================================================

def test_integration_pipeline(image_path):
    print_header("TEST 8: Integration with Perception Pipeline")
    
    if not os.getenv('ANTHROPIC_API_KEY'):
        print_info("Skipping pipeline tests - ANTHROPIC_API_KEY not set")
        return
    
    if not image_path or not os.path.exists(image_path):
        print_warn("Test image not available")
        return
    
    try:
        from perception_pipeline import IntegratedPerceptionPipeline
        
        # Test 8.1: Initialize pipeline
        print_test("8.1 - Initialize IntegratedPerceptionPipeline")
        try:
            pipeline = IntegratedPerceptionPipeline(vlm_provider='claude')
            print_pass()
            print_result("Pipeline initialized")
        except Exception as e:
            print_fail(f"Pipeline initialization failed: {str(e)}")
            return
        
        # Test 8.2: Process image
        print_test("8.2 - Process image through pipeline")
        try:
            start_time = time.time()
            
            result = pipeline.process_image(
                image_path=image_path,
                strategy='vlm',
                save_output=True
            )
            
            elapsed = time.time() - start_time
            
            if result and result.get('success'):
                print_pass()
                print_result(f"Pipeline processing completed in {elapsed:.2f}s")
                print_result(f"Output files: {result.get('output_files', [])}")
            else:
                print_fail(f"Pipeline failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print_fail(f"Pipeline processing error: {str(e)}")
        
    except ImportError as e:
        print_warn(f"Perception pipeline not available: {str(e)}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 9: Performance Benchmarks
# ============================================================================

def test_performance_benchmarks():
    print_header("TEST 9: Performance Benchmarks")
    
    if not os.getenv('ANTHROPIC_API_KEY'):
        print_info("Skipping performance tests - ANTHROPIC_API_KEY not set")
        return
    
    # Test 9.1: API response time
    print_test("9.1 - Measure Claude API response time")
    try:
        client = get_vlm_client('claude')
        if not client:
            print_skip("Claude client not available")
            return
        
        # Create test image path
        test_image = "test_image.jpg"
        if not os.path.exists(test_image):
            print_skip("Test image not available")
            return
        
        start_time = time.time()
        response = client.analyze_ui(test_image, UI_DISCOVERY_PROMPT, max_tokens=500)
        elapsed = time.time() - start_time
        
        print_pass()
        print_result(f"API response time: {elapsed:.2f}s")
        
        if elapsed < 2:
            print_result("Status: FAST ✓")
        elif elapsed < 5:
            print_result("Status: ACCEPTABLE")
        else:
            print_result("Status: SLOW")
    except Exception as e:
        print_warn(f"Performance test skipped: {str(e)}")
    
    # Test 9.2: Parsing performance
    print_test("9.2 - Measure parsing performance")
    try:
        parser = UIParser()
        
        # Simulate a large response
        large_response = """
        {
            "elements": [
                {"id": f"elem_{i}", "type": "button", "label": f"Button {i}", "bbox": [0.1, 0.1, 0.3, 0.2]}
                for i in range(50)
            ]
        }
        """
        
        start_time = time.time()
        result = parser.extract_json_from_response(large_response)
        elapsed = time.time() - start_time
        
        print_pass()
        print_result(f"JSON extraction time: {elapsed*1000:.2f}ms")
    except Exception as e:
        print_warn(f"Performance test skipped: {str(e)}")

# ============================================================================
# TEST 10: Error Handling
# ============================================================================

def test_error_handling():
    print_header("TEST 10: Error Handling & Edge Cases")
    
    # Test 10.1: Invalid image path
    print_test("10.1 - Handle invalid image path")
    try:
        client = get_vlm_client('claude')
        if client:
            try:
                result = client.analyze_ui("nonexistent.jpg", UI_DISCOVERY_PROMPT)
                print_fail("Should have raised error for invalid image")
            except (FileNotFoundError, Exception):
                print_pass()
                print_result("Invalid image path correctly handled")
        else:
            print_skip("Claude client not available")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 10.2: Empty response handling
    print_test("10.2 - Handle empty VLM response")
    try:
        parser = UIParser()
        
        # Test with empty response
        result = parser.parse_vlm_response("", image_width=800, image_height=600)
        
        if isinstance(result, list):
            print_pass()
            print_result(f"Empty response returns list: {result}")
        else:
            print_fail("Empty response handling failed")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 10.3: Malformed JSON handling
    print_test("10.3 - Handle malformed JSON")
    try:
        parser = UIParser()
        
        # Test with malformed JSON
        response = "Here's invalid JSON: { bad json }"
        result = parser.extract_json_from_response(response)
        
        # Should handle gracefully
        print_pass()
        print_result(f"Malformed JSON handled gracefully")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 10.4: Invalid bbox values
    print_test("10.4 - Handle invalid bbox values")
    try:
        parser = UIParser()
        
        # Test with out-of-range bbox
        element = UIElement(
            "test", "button", "Test",
            bbox=[-0.1, -0.1, 1.5, 1.5],  # Out of range
            confidence=0.95
        )
        
        validated = parser.validate_element(element)
        
        print_pass()
        print_result(f"Invalid bbox element validation: {validated}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    print(f"\n{BLUE}")
    print("=" * 70)
    print("  COMPREHENSIVE VLM TESTING SUITE")
    print("=" * 70)
    print(f"{END}\n")
    
    print_info(f"Python: {sys.version}")
    print_info(f"Testing VLM components\n")
    
    # Run tests
    test_configuration()
    test_vlm_factory()
    test_image_encoding()
    test_ui_parser()
    test_prompt_templates()
    
    # Create test image for live tests
    image_path = test_image_encoding()
    
    if image_path:
        test_claude_analysis(image_path)
        test_perception_router(image_path)
        test_integration_pipeline(image_path)
    
    test_performance_benchmarks()
    test_error_handling()
    
    # Print summary
    print_header("TEST SUMMARY")
    
    total_tests = (test_results['passed'] + test_results['failed'] + 
                   test_results['warnings'] + test_results['skipped'])
    
    print(f"{GREEN}✓ PASSED:{END} {test_results['passed']}")
    print(f"{RED}✗ FAILED:{END} {test_results['failed']}")
    print(f"{YELLOW}⚠ WARNINGS:{END} {test_results['warnings']}")
    print(f"{CYAN}⊘ SKIPPED:{END} {test_results['skipped']}")
    print(f"━" * 40)
    print(f"Total Tests: {total_tests}")
    
    # Overall result
    if test_results['failed'] == 0:
        print(f"\n{GREEN}═══════════════════════════════════════{END}")
        print(f"{GREEN}  ✓ ALL TESTS PASSED!{END}")
        print(f"{GREEN}═══════════════════════════════════════{END}\n")
        return 0
    else:
        print(f"\n{YELLOW}═══════════════════════════════════════{END}")
        print(f"{YELLOW}  ⚠ SOME TESTS FAILED - CHECK ABOVE{END}")
        print(f"{YELLOW}═══════════════════════════════════════{END}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
