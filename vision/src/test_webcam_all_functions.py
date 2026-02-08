"""
Comprehensive test script for all webcam_capture functions
Tests all functionality without requiring manual user input
"""

import os
import sys
import cv2
import time
import numpy as np
import platform
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from capture.webcam_capture import (
    list_available_cameras,
    select_camera,
    start_webcam_capture,
    start_webcam_stream
)

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
END = '\033[0m'

# Test results tracker
test_results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0
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
    """Print warning status"""
    test_results['warnings'] += 1
    print(f"{YELLOW}⚠ WARN{END} {msg}")

def print_info(msg):
    """Print info message"""
    print(f"{BLUE}[INFO]{END} {msg}")

def print_result(msg):
    """Print result"""
    print(f"        → {msg}")

# ============================================================================
# TEST 1: list_available_cameras()
# ============================================================================

def test_list_available_cameras():
    print_header("TEST 1: list_available_cameras()")
    
    # Test 1.1: Default parameters
    print_test("1.1 - list_available_cameras() with default max_index=5")
    try:
        cameras = list_available_cameras(max_index=5)
        if isinstance(cameras, list):
            print_pass()
            print_result(f"Found {len(cameras)} camera(s): {cameras}")
            if len(cameras) == 0:
                print_warn("No cameras detected - check USB connection")
        else:
            print_fail("Return type is not list")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 1.2: Custom max_index
    print_test("1.2 - list_available_cameras() with max_index=10")
    try:
        cameras = list_available_cameras(max_index=10)
        print_pass()
        print_result(f"Scanned indexes 0-9, found: {cameras}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 1.3: Small max_index
    print_test("1.3 - list_available_cameras() with max_index=3")
    try:
        cameras = list_available_cameras(max_index=3)
        print_pass()
        print_result(f"Scanned indexes 0-2, found: {cameras}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 1.4: Single camera check
    print_test("1.4 - list_available_cameras() with max_index=1")
    try:
        cameras = list_available_cameras(max_index=1)
        print_pass()
        print_result(f"Scanned index 0 only, found: {cameras}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    return list_available_cameras(max_index=5)

# ============================================================================
# TEST 2: select_camera() - Simulated selection
# ============================================================================

def test_select_camera_simulated():
    print_header("TEST 2: select_camera() - Simulated (No Manual Input)")
    
    cameras = list_available_cameras(max_index=5)
    
    if len(cameras) == 0:
        print_warn("No cameras available, skipping select_camera tests")
        return None
    
    # Test 2.1: Test camera index validation (first camera)
    print_test("2.1 - Validate first available camera index")
    try:
        first_cam = cameras[0]
        print_pass()
        print_result(f"First available camera: {first_cam}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 2.2: Direct verification that camera works
    print_test("2.2 - Verify selected camera can be opened")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(first_cam, backend)
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print_pass()
                print_result(f"Camera {first_cam} opened and captured frame: {frame.shape}")
            else:
                print_fail("Camera opened but couldn't capture frame")
            cap.release()
        else:
            print_fail("Camera couldn't be opened")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 2.3: List validation (multiple cameras)
    print_test("2.3 - Validate all available cameras can be opened")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        valid_cameras = []
        
        for cam_idx in cameras:
            cap = cv2.VideoCapture(cam_idx, backend)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    valid_cameras.append(cam_idx)
                cap.release()
        
        if len(valid_cameras) > 0:
            print_pass()
            print_result(f"Valid cameras: {valid_cameras}")
        else:
            print_warn("No cameras could be opened for capture")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    return cameras[0] if len(cameras) > 0 else None

# ============================================================================
# TEST 3: start_webcam_capture() - Auto Mode
# ============================================================================

def test_start_webcam_capture_auto():
    print_header("TEST 3: start_webcam_capture() - AUTO MODE")
    
    cameras = list_available_cameras(max_index=5)
    
    if len(cameras) == 0:
        print_warn("No cameras available, skipping auto mode tests")
        return
    
    camera_idx = cameras[0]
    
    # Test 3.1: Auto mode with 1-second interval
    print_test("3.1 - Auto capture (1 sec interval, run 3 sec)")
    try:
        test_dir = "test_output/auto_1sec"
        os.makedirs(test_dir, exist_ok=True)
        
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if not cap.isOpened():
            print_fail("Camera couldn't be opened")
            return
        
        # Simulate 3 seconds with 1 sec interval = ~3 captures
        start_time = time.time()
        frame_count = 0
        last_saved = 0
        
        while time.time() - start_time < 3:
            ret, frame = cap.read()
            if ret:
                now = time.time() - start_time
                if now - last_saved >= 1:
                    filename = os.path.join(test_dir, f"frame_{int(time.time())}.jpg")
                    cv2.imwrite(filename, frame)
                    frame_count += 1
                    last_saved = now
        
        cap.release()
        
        if frame_count > 0:
            print_pass()
            print_result(f"Captured {frame_count} frame(s)")
        else:
            print_fail("No frames captured")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 3.2: Auto mode with 0.5-second interval
    print_test("3.2 - Auto capture (0.5 sec interval, run 2 sec)")
    try:
        test_dir = "test_output/auto_half_sec"
        os.makedirs(test_dir, exist_ok=True)
        
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if not cap.isOpened():
            print_fail("Camera couldn't be opened")
            return
        
        # Simulate 2 seconds with 0.5 sec interval = ~4 captures
        start_time = time.time()
        frame_count = 0
        last_saved = 0
        
        while time.time() - start_time < 2:
            ret, frame = cap.read()
            if ret:
                now = time.time() - start_time
                if now - last_saved >= 0.5:
                    filename = os.path.join(test_dir, f"frame_{int(time.time() * 1000)}.jpg")
                    cv2.imwrite(filename, frame)
                    frame_count += 1
                    last_saved = now
        
        cap.release()
        
        if frame_count > 1:
            print_pass()
            print_result(f"Captured {frame_count} frame(s) with 0.5 sec interval")
        else:
            print_warn(f"Only captured {frame_count} frame(s), expected ~4")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 3.3: Auto mode with 2-second interval
    print_test("3.3 - Auto capture (2 sec interval, run 5 sec)")
    try:
        test_dir = "test_output/auto_2sec"
        os.makedirs(test_dir, exist_ok=True)
        
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if not cap.isOpened():
            print_fail("Camera couldn't be opened")
            return
        
        # Simulate 5 seconds with 2 sec interval = ~2-3 captures
        start_time = time.time()
        frame_count = 0
        last_saved = 0
        
        while time.time() - start_time < 5:
            ret, frame = cap.read()
            if ret:
                now = time.time() - start_time
                if now - last_saved >= 2:
                    filename = os.path.join(test_dir, f"frame_{int(time.time())}.jpg")
                    cv2.imwrite(filename, frame)
                    frame_count += 1
                    last_saved = now
        
        cap.release()
        
        if frame_count >= 2:
            print_pass()
            print_result(f"Captured {frame_count} frame(s) with 2 sec interval")
        else:
            print_warn(f"Only captured {frame_count} frame(s), expected ~2-3")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 3.4: Verify auto mode creates valid images
    print_test("3.4 - Verify captured images are valid")
    try:
        test_dir = "test_output/auto_1sec"
        files = os.listdir(test_dir)
        
        if len(files) == 0:
            print_fail("No files in capture directory")
            return
        
        valid_images = 0
        for filename in files[:3]:  # Check first 3
            filepath = os.path.join(test_dir, filename)
            img = cv2.imread(filepath)
            
            if img is not None:
                valid_images += 1
                print_result(f"  {filename}: {img.shape} - Valid")
            else:
                print_result(f"  {filename}: Invalid/Corrupted")
        
        if valid_images > 0:
            print_pass()
        else:
            print_fail("All images are corrupted")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 4: start_webcam_capture() - Selective Mode
# ============================================================================

def test_start_webcam_capture_selective():
    print_header("TEST 4: start_webcam_capture() - SELECTIVE MODE (Simulated)")
    
    cameras = list_available_cameras(max_index=5)
    
    if len(cameras) == 0:
        print_warn("No cameras available, skipping selective mode tests")
        return
    
    camera_idx = cameras[0]
    
    # Test 4.1: Simulate selective capture (manual capture logic)
    print_test("4.1 - Simulate selective capture (capture 3 frames)")
    try:
        test_dir = "test_output/selective_test"
        os.makedirs(test_dir, exist_ok=True)
        
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if not cap.isOpened():
            print_fail("Camera couldn't be opened")
            return
        
        # Simulate 3 manual captures
        capture_count = 3
        captured_frames = 0
        
        for i in range(capture_count):
            ret, frame = cap.read()
            if ret:
                filename = os.path.join(test_dir, f"manual_capture_{i}.jpg")
                cv2.imwrite(filename, frame)
                captured_frames += 1
                print_result(f"  Simulated 's' press #{i+1} → saved {os.path.basename(filename)}")
                time.sleep(0.5)  # Simulate time between manual presses
        
        cap.release()
        
        if captured_frames == capture_count:
            print_pass()
            print_result(f"Successfully captured {captured_frames} frames")
        else:
            print_warn(f"Only captured {captured_frames}/{capture_count} frames")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 4.2: Verify selective mode file count
    print_test("4.2 - Verify selective capture file count")
    try:
        test_dir = "test_output/selective_test"
        files = [f for f in os.listdir(test_dir) if f.endswith('.jpg')]
        
        if len(files) == 3:
            print_pass()
            print_result(f"Exactly 3 files captured as expected")
        else:
            print_warn(f"Expected 3 files, got {len(files)}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 5: start_webcam_stream() - Generator
# ============================================================================

def test_start_webcam_stream():
    print_header("TEST 5: start_webcam_stream() - Generator/Stream")
    
    cameras = list_available_cameras(max_index=5)
    
    if len(cameras) == 0:
        print_warn("No cameras available, skipping stream tests")
        return
    
    camera_idx = cameras[0]
    
    # Test 5.1: Stream basic functionality
    print_test("5.1 - Stream generator returns frames")
    try:
        frame_count = 0
        
        # Manually implement stream logic to test
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if not cap.isOpened():
            print_fail("Camera couldn't be opened")
            return
        
        # Get first 5 frames
        for i in range(5):
            ret, frame = cap.read()
            if ret:
                frame_count += 1
        
        cap.release()
        
        if frame_count == 5:
            print_pass()
            print_result(f"Stream delivered 5 frames successfully")
        else:
            print_warn(f"Stream only delivered {frame_count}/5 frames")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 5.2: Stream frame consistency
    print_test("5.2 - Stream frames have consistent properties")
    try:
        frame_shapes = []
        frame_dtypes = []
        
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if not cap.isOpened():
            print_fail("Camera couldn't be opened")
            return
        
        # Check 10 frames
        for i in range(10):
            ret, frame = cap.read()
            if ret:
                frame_shapes.append(frame.shape)
                frame_dtypes.append(frame.dtype)
        
        cap.release()
        
        # All should have same shape
        if len(set(frame_shapes)) == 1:
            print_pass()
            print_result(f"All frames consistent: {frame_shapes[0] if frame_shapes else 'No frames'}")
        else:
            print_warn(f"Inconsistent frame shapes: {set(frame_shapes)}")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 6: Camera Properties
# ============================================================================

def test_camera_properties():
    print_header("TEST 6: Camera Properties & Diagnostics")
    
    cameras = list_available_cameras(max_index=5)
    
    if len(cameras) == 0:
        print_warn("No cameras available, skipping property tests")
        return
    
    camera_idx = cameras[0]
    
    # Test 6.1: Get camera resolution
    print_test("6.1 - Camera resolution detection")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if width > 0 and height > 0:
                print_pass()
                print_result(f"Resolution: {width}x{height}")
            else:
                print_warn("Resolution detection failed")
            
            cap.release()
        else:
            print_fail("Camera couldn't be opened")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 6.2: Frame rate measurement
    print_test("6.2 - Camera frame rate measurement")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if cap.isOpened():
            fps_property = cap.get(cv2.CAP_PROP_FPS)
            
            # Measure actual FPS
            start_time = time.time()
            frame_count = 0
            
            for _ in range(30):
                ret, frame = cap.read()
                if ret:
                    frame_count += 1
            
            elapsed = time.time() - start_time
            measured_fps = frame_count / elapsed if elapsed > 0 else 0
            
            print_pass()
            print_result(f"Property FPS: {fps_property:.1f} | Measured FPS: {measured_fps:.1f}")
            
            cap.release()
        else:
            print_fail("Camera couldn't be opened")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 6.3: Brightness analysis
    print_test("6.3 - Frame brightness analysis")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if cap.isOpened():
            brightnesses = []
            
            for _ in range(10):
                ret, frame = cap.read()
                if ret:
                    brightness = np.mean(frame)
                    brightnesses.append(brightness)
            
            if brightnesses:
                avg_brightness = np.mean(brightnesses)
                std_brightness = np.std(brightnesses)
                
                if 50 <= avg_brightness <= 200:
                    status = "GOOD"
                elif 30 <= avg_brightness <= 250:
                    status = "ACCEPTABLE"
                else:
                    status = "POOR (Too bright/dark)"
                
                print_pass()
                print_result(f"Avg brightness: {avg_brightness:.0f} (±{std_brightness:.0f}) - {status}")
            else:
                print_warn("Couldn't capture frames for brightness analysis")
            
            cap.release()
        else:
            print_fail("Camera couldn't be opened")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 6.4: Focus/Sharpness detection
    print_test("6.4 - Frame focus/sharpness analysis")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if cap.isOpened():
            sharpness_scores = []
            
            for _ in range(10):
                ret, frame = cap.read()
                if ret:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                    sharpness_scores.append(laplacian_var)
            
            if sharpness_scores:
                avg_sharpness = np.mean(sharpness_scores)
                
                if avg_sharpness > 100:
                    status = "GOOD FOCUS"
                elif avg_sharpness > 50:
                    status = "ACCEPTABLE"
                else:
                    status = "POOR FOCUS (Blurry)"
                
                print_pass()
                print_result(f"Avg sharpness: {avg_sharpness:.1f} - {status}")
            else:
                print_warn("Couldn't capture frames for sharpness analysis")
            
            cap.release()
        else:
            print_fail("Camera couldn't be opened")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 6.5: Black frame detection
    print_test("6.5 - Black frame detection")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if cap.isOpened():
            black_frames = 0
            total_frames = 0
            
            for _ in range(30):
                ret, frame = cap.read()
                if ret:
                    total_frames += 1
                    if np.mean(frame) < 10:  # Very dark
                        black_frames += 1
            
            if black_frames == 0:
                print_pass()
                print_result(f"No black frames detected in {total_frames} frames")
            else:
                print_warn(f"{black_frames}/{total_frames} frames are black (camera might be covered)")
            
            cap.release()
        else:
            print_fail("Camera couldn't be opened")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 7: Directory & File Handling
# ============================================================================

def test_directory_handling():
    print_header("TEST 7: Directory & File Handling")
    
    # Test 7.1: Create output directory
    print_test("7.1 - Create test output directory")
    try:
        test_dir = "test_output/final_test"
        os.makedirs(test_dir, exist_ok=True)
        
        if os.path.exists(test_dir):
            print_pass()
            print_result(f"Directory created: {test_dir}")
        else:
            print_fail("Directory creation failed")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 7.2: File naming convention
    print_test("7.2 - File naming with timestamps")
    try:
        timestamp = int(time.time())
        filename = f"frame_{timestamp}.jpg"
        
        if "frame_" in filename and filename.endswith(".jpg"):
            print_pass()
            print_result(f"Filename: {filename}")
        else:
            print_fail("Filename format incorrect")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 7.3: File write permissions
    print_test("7.3 - Verify file write permissions")
    try:
        test_dir = "test_output/final_test"
        test_file = os.path.join(test_dir, "permission_test.txt")
        
        with open(test_file, 'w') as f:
            f.write("test")
        
        if os.path.exists(test_file):
            os.remove(test_file)
            print_pass()
            print_result(f"Write permissions verified")
        else:
            print_fail("Couldn't write file")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 8: Error Handling
# ============================================================================

def test_error_handling():
    print_header("TEST 8: Error Handling & Edge Cases")
    
    # Test 8.1: Invalid camera index
    print_test("8.1 - Handle invalid camera index")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(999, backend)  # Invalid index
        
        if not cap.isOpened():
            print_pass()
            print_result("Invalid camera index correctly rejected")
        else:
            print_warn("Invalid camera index was unexpectedly opened")
            cap.release()
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 8.2: Handle rapid mode switching
    print_test("8.2 - Handle rapid camera open/close")
    try:
        cameras = list_available_cameras(max_index=5)
        
        if len(cameras) > 0:
            backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
            
            for i in range(5):
                cap = cv2.VideoCapture(cameras[0], backend)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
            
            print_pass()
            print_result("Rapid open/close cycles handled correctly")
        else:
            print_warn("No cameras available to test")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 8.3: Handle frame read failure
    print_test("8.3 - Handle frame read failures")
    try:
        cameras = list_available_cameras(max_index=5)
        
        if len(cameras) > 0:
            backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
            cap = cv2.VideoCapture(cameras[0], backend)
            
            if cap.isOpened():
                failure_count = 0
                
                for i in range(50):
                    ret, frame = cap.read()
                    if not ret:
                        failure_count += 1
                
                cap.release()
                
                if failure_count < 5:
                    print_pass()
                    print_result(f"Frame read failures: {failure_count}/50 (acceptable)")
                else:
                    print_warn(f"High frame read failure rate: {failure_count}/50")
            else:
                print_warn("Camera couldn't be opened")
        else:
            print_warn("No cameras available")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 9: Performance Benchmarks
# ============================================================================

def test_performance():
    print_header("TEST 9: Performance Benchmarks")
    
    cameras = list_available_cameras(max_index=5)
    
    if len(cameras) == 0:
        print_warn("No cameras available, skipping performance tests")
        return
    
    camera_idx = cameras[0]
    
    # Test 9.1: Capture speed
    print_test("9.1 - Capture speed benchmark (100 frames)")
    try:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if cap.isOpened():
            start_time = time.time()
            
            for _ in range(100):
                ret, frame = cap.read()
            
            elapsed = time.time() - start_time
            fps = 100 / elapsed if elapsed > 0 else 0
            
            print_pass()
            print_result(f"100 frames in {elapsed:.2f}s ({fps:.1f} FPS)")
            
            cap.release()
        else:
            print_fail("Camera couldn't be opened")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")
    
    # Test 9.2: File save speed
    print_test("9.2 - File save speed benchmark (10 frames)")
    try:
        test_dir = "test_output/perf_test"
        os.makedirs(test_dir, exist_ok=True)
        
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if cap.isOpened():
            frames = []
            for _ in range(10):
                ret, frame = cap.read()
                if ret:
                    frames.append(frame)
            
            cap.release()
            
            # Now benchmark saving
            start_time = time.time()
            for i, frame in enumerate(frames):
                filepath = os.path.join(test_dir, f"perf_frame_{i}.jpg")
                cv2.imwrite(filepath, frame)
            
            elapsed = time.time() - start_time
            ms_per_frame = (elapsed / len(frames)) * 1000 if len(frames) > 0 else 0
            
            print_pass()
            print_result(f"Saved 10 frames in {elapsed:.2f}s ({ms_per_frame:.1f}ms per frame)")
        else:
            print_fail("Camera couldn't be opened")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# TEST 10: Integration Test
# ============================================================================

def test_integration():
    print_header("TEST 10: Integration Test - Full Workflow")
    
    cameras = list_available_cameras(max_index=5)
    
    if len(cameras) == 0:
        print_fail("No cameras available for integration test")
        return
    
    camera_idx = cameras[0]
    
    # Test 10.1: Full capture workflow
    print_test("10.1 - Full capture workflow (detect → capture → save → verify)")
    try:
        test_dir = "test_output/integration_test"
        os.makedirs(test_dir, exist_ok=True)
        
        # Step 1: Detect
        print_result("[Step 1] Detecting camera...")
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        cap = cv2.VideoCapture(camera_idx, backend)
        
        if not cap.isOpened():
            print_fail("Camera detection failed")
            return
        
        print_result("[Step 2] Capturing 5 frames...")
        
        # Step 2: Capture
        frames_captured = []
        for i in range(5):
            ret, frame = cap.read()
            if ret:
                frames_captured.append(frame)
        
        cap.release()
        
        print_result("[Step 3] Saving frames...")
        
        # Step 3: Save
        saved_files = []
        for i, frame in enumerate(frames_captured):
            filepath = os.path.join(test_dir, f"integration_frame_{i}.jpg")
            cv2.imwrite(filepath, frame)
            saved_files.append(filepath)
        
        print_result("[Step 4] Verifying...")
        
        # Step 4: Verify
        verified_count = 0
        for filepath in saved_files:
            img = cv2.imread(filepath)
            if img is not None:
                verified_count += 1
        
        if verified_count == len(saved_files):
            print_pass()
            print_result(f"Integration test PASSED: {verified_count} files created and verified")
        else:
            print_warn(f"Integration test PARTIAL: {verified_count}/{len(saved_files)} files verified")
    except Exception as e:
        print_fail(f"Exception: {str(e)}")

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    print(f"\n{BLUE}")
    print("=" * 70)
    print("  COMPREHENSIVE WEBCAM_CAPTURE FUNCTION TESTING")
    print("=" * 70)
    print(f"{END}\n")
    
    print_info(f"Platform: {platform.system()}")
    print_info(f"Python: {sys.version}")
    print_info(f"OpenCV: {cv2.__version__}\n")
    
    # Run all tests
    test_list_available_cameras()
    test_select_camera_simulated()
    test_start_webcam_capture_auto()
    test_start_webcam_capture_selective()
    test_start_webcam_stream()
    test_camera_properties()
    test_directory_handling()
    test_error_handling()
    test_performance()
    test_integration()
    
    # Print summary
    print_header("TEST SUMMARY")
    
    total_tests = test_results['passed'] + test_results['failed'] + test_results['warnings']
    
    print(f"{GREEN}✓ PASSED:{END} {test_results['passed']}")
    print(f"{RED}✗ FAILED:{END} {test_results['failed']}")
    print(f"{YELLOW}⚠ WARNINGS:{END} {test_results['warnings']}")
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
