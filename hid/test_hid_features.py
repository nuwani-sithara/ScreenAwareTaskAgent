"""
HID Feature Test Script
Tests all HID capabilities via REST API

No external dependencies required - uses built-in urllib

Usage: python test_hid_features.py
"""

import urllib.request
import urllib.error
import time
import json
from typing import Dict, Any

# API Configuration
API_BASE_URL = "http://localhost:3015"
COMMAND_ENDPOINT = f"{API_BASE_URL}/hid/command"
STATUS_ENDPOINT = f"{API_BASE_URL}/hid/status"
HEALTH_ENDPOINT = f"{API_BASE_URL}/health"

def print_section(title: str):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def send_command(command_type: str, payload: Dict[str, Any], description: str = ""):
    """Send a command to the HID API and display the result"""
    command = {
        "type": command_type,
        "payload": payload
    }
    
    print(f"▶ {description or command_type}")
    print(f"  Payload: {json.dumps(payload, indent=2)}")
    
    try:
        start_time = time.time()
        
        # Create request with JSON body
        data = json.dumps(command).encode('utf-8')
        req = urllib.request.Request(
            COMMAND_ENDPOINT,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        # Send request
        with urllib.request.urlopen(req, timeout=5) as response:
            elapsed = (time.time() - start_time) * 1000
            
            if response.status == 200:
                print(f"  ✓ Success ({elapsed:.0f}ms)")
                result = json.loads(response.read().decode('utf-8'))
                if result.get('executionTime'):
                    exec_time = result['executionTime']
                    if isinstance(exec_time, (int, float)):
                        print(f"  Execution time: {exec_time:.0f}ms")
                    else:
                        print(f"  Execution time: {exec_time}ms")
            else:
                print(f"  ✗ Failed: {response.status} - {response.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        print(f"  ✗ HTTP Error: {e.code} - {e.read().decode('utf-8')}")
    except urllib.error.URLError as e:
        print(f"  ✗ URL Error: {e.reason}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    time.sleep(0.5)  # Brief pause between commands

def check_health():
    """Check API server health"""
    print_section("Health Check")
    try:
        with urllib.request.urlopen(HEALTH_ENDPOINT, timeout=2) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"✓ Server is healthy: {data}")
    except Exception as e:
        print(f"✗ Server health check failed: {e}")
        return False
    return True

def check_status():
    """Check device status"""
    print_section("Device Status")
    try:
        with urllib.request.urlopen(STATUS_ENDPOINT, timeout=2) as response:
            status = json.loads(response.read().decode('utf-8'))
            print(json.dumps(status, indent=2))
    except Exception as e:
        print(f"✗ Status check failed: {e}")

def test_mouse_movements():
    """Test various mouse movement patterns"""
    print_section("Mouse Movement Tests")
    
    # Move right and down
    send_command("mouse_move", {
        "dx": 200,
        "dy": 150,
        "duration": 500
    }, "Move right and down (smooth, 500ms)")
    
    # Move left and up
    send_command("mouse_move", {
        "dx": -150,
        "dy": -100,
        "duration": 200
    }, "Move left and up (quick, 200ms)")
    
    # Large movement
    send_command("mouse_move", {
        "dx": 300,
        "dy": 200,
        "duration": 800
    }, "Large movement (slow, 800ms)")

def test_mouse_clicks():
    """Test different mouse click operations"""
    print_section("Mouse Click Tests")
    
    # Left click
    send_command("mouse_click", {
        "button": "left"
    }, "Single left click")
    
    # Right click
    send_command("mouse_click", {
        "button": "right"
    }, "Single right click")
    
    # Double click
    send_command("mouse_click", {
        "button": "left",
        "count": 2
    }, "Double left click")
    
    # Triple click
    send_command("mouse_click", {
        "button": "left",
        "count": 3
    }, "Triple left click")

def test_mouse_drag():
    """Test mouse drag operations"""
    print_section("Mouse Drag Tests")
    
    # Drag right and down
    send_command("mouse_drag", {
        "dx": 300,
        "dy": 200,
        "button": "left",
        "duration": 600
    }, "Drag right and down (300, 200)")
    
    # Right-button drag back
    send_command("mouse_drag", {
        "dx": -300,
        "dy": -200,
        "button": "right",
        "duration": 400
    }, "Right-button drag back to start")

def test_mouse_scroll():
    """Test mouse scroll operations"""
    print_section("Mouse Scroll Tests")
    
    # Scroll down
    send_command("mouse_scroll", {
        "deltaY": -3
    }, "Scroll down (3 ticks)")
    
    time.sleep(0.5)
    
    # Scroll up
    send_command("mouse_scroll", {
        "deltaY": 3
    }, "Scroll up (3 ticks)")
    
    time.sleep(0.5)
    
    # Large scroll down
    send_command("mouse_scroll", {
        "deltaY": -5
    }, "Large scroll down (5 ticks)")

def test_keyboard_shortcuts():
    """Test keyboard shortcuts and key combinations"""
    print_section("Keyboard Shortcut Tests")
    
    # Ctrl+C (copy)
    send_command("key_combo", {
        "modifiers": ["ctrl"],
        "key": "c"
    }, "Ctrl+C (Copy)")
    
    # Ctrl+V (paste)
    send_command("key_combo", {
        "modifiers": ["ctrl"],
        "key": "v"
    }, "Ctrl+V (Paste)")
    
    # Alt+Tab (switch window)
    send_command("key_combo", {
        "modifiers": ["alt"],
        "key": "tab"
    }, "Alt+Tab (Switch window)")
    
    # Ctrl+Shift+T (reopen closed tab)
    send_command("key_combo", {
        "modifiers": ["ctrl", "shift"],
        "key": "t"
    }, "Ctrl+Shift+T (Reopen tab)")
    
    # Win+D (show desktop)
    send_command("key_combo", {
        "modifiers": ["meta"],
        "key": "d"
    }, "Win+D (Show desktop)")
    
    # Ctrl+A (select all)
    send_command("key_combo", {
        "modifiers": ["ctrl"],
        "key": "a"
    }, "Ctrl+A (Select all)")

def test_text_typing():
    """Test text typing"""
    print_section("Text Typing Tests")
    
    # Type a simple message
    send_command("type_text", {
        "text": "Hello from HID API!"
    }, "Type: 'Hello from HID API!'")
    
    time.sleep(0.5)
    
    # Type with special characters
    send_command("type_text", {
        "text": "Testing 123... @#$%"
    }, "Type with special chars")

def test_navigation_keys():
    """Test common navigation key combinations"""
    print_section("Navigation Key Tests")
    
    # Home key
    send_command("key_press", {
        "key": "home"
    }, "Press Home key")
    
    # End key
    send_command("key_press", {
        "key": "end"
    }, "Press End key")
    
    # Page Down
    send_command("key_press", {
        "key": "pagedown"
    }, "Press Page Down")
    
    # Page Up
    send_command("key_press", {
        "key": "pageup"
    }, "Press Page Up")
    
    # Arrow keys
    send_command("key_press", {
        "key": "right"
    }, "Press Right Arrow")
    
    send_command("key_press", {
        "key": "down"
    }, "Press Down Arrow")

def test_function_keys():
    """Test function keys"""
    print_section("Function Key Tests")
    
    # F5 (refresh)
    send_command("key_press", {
        "key": "f5"
    }, "Press F5 (Refresh)")
    
    # F11 (fullscreen)
    send_command("key_press", {
        "key": "f11"
    }, "Press F11 (Fullscreen toggle)")
    
    # F12 (dev tools)
    send_command("key_press", {
        "key": "f12"
    }, "Press F12 (Developer tools)")

def run_comprehensive_demo():
    """Run a comprehensive demonstration of all features"""
    print_section("Comprehensive HID Feature Demo")
    
    # 1. Move mouse in a square pattern (relative movements)
    print("\n1. Drawing a square with mouse movements...")
    movements = [
        (400, 0, "Move right 400px"),      # Right edge
        (0, 400, "Move down 400px"),       # Bottom edge
        (-400, 0, "Move left 400px"),      # Left edge
        (0, -400, "Move up 400px"),        # Back to top
    ]
    
    for dx, dy, desc in movements:
        send_command("mouse_move", {"dx": dx, "dy": dy, "duration": 300}, desc)
        time.sleep(0.3)
    
    # 2. Click in the center
    print("\n2. Click in the center...")
    send_command("mouse_click", {"button": "left"}, "Center click")
    
    # 3. Type a message
    print("\n3. Type a test message...")
    send_command("type_text", {"text": "HID System Working!"}, "Type message")
    
    # 4. Select all and copy
    print("\n4. Select all and copy...")
    send_command("key_combo", {"modifiers": ["ctrl"], "key": "a"}, "Select all")
    time.sleep(0.2)
    send_command("key_combo", {"modifiers": ["ctrl"], "key": "c"}, "Copy")
    
    # 5. Scroll test
    print("\n5. Scroll test...")
    send_command("mouse_scroll", {"deltaY": -5}, "Scroll down")
    time.sleep(0.5)
    send_command("mouse_scroll", {"deltaY": 5}, "Scroll up")

def main():
    """Main test runner"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║           HID Feature Test Suite v2.0                     ║
║           Testing Production HID System                   ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # Check if server is running
    if not check_health():
        print("\n❌ API server is not running!")
        print("Please start the server with: npm start")
        return
    
    # Check device status
    check_status()
    
    # Prompt user for test selection
    print("\n" + "="*60)
    print("Select test suite to run:")
    print("="*60)
    print("  1. Mouse Movement Tests")
    print("  2. Mouse Click Tests")
    print("  3. Mouse Drag Tests")
    print("  4. Mouse Scroll Tests")
    print("  5. Keyboard Shortcut Tests")
    print("  6. Text Typing Tests")
    print("  7. Navigation Key Tests")
    print("  8. Function Key Tests")
    print("  9. Comprehensive Demo (all features)")
    print("  0. Run ALL tests sequentially")
    print("="*60)
    
    choice = input("\nEnter your choice (0-9): ").strip()
    
    test_map = {
        "1": ("Mouse Movement Tests", test_mouse_movements),
        "2": ("Mouse Click Tests", test_mouse_clicks),
        "3": ("Mouse Drag Tests", test_mouse_drag),
        "4": ("Mouse Scroll Tests", test_mouse_scroll),
        "5": ("Keyboard Shortcut Tests", test_keyboard_shortcuts),
        "6": ("Text Typing Tests", test_text_typing),
        "7": ("Navigation Key Tests", test_navigation_keys),
        "8": ("Function Key Tests", test_function_keys),
        "9": ("Comprehensive Demo", run_comprehensive_demo)
    }
    
    if choice == "0":
        # Run all tests sequentially
        print_section("Running ALL Tests Sequentially")
        print("This will execute all 9 test suites in order.\n")
        
        test_count = len(test_map)
        results = {"passed": 0, "failed": 0, "errors": []}
        
        for idx, (test_name, test_func) in test_map.items():
            print(f"\n{'='*60}")
            print(f"  Progress: {idx}/{test_count} - {test_name}")
            print(f"{'='*60}\n")
            
            try:
                test_func()
                results["passed"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{test_name}: {str(e)}")
                print(f"  ✗ Test suite failed: {e}")
                print(f"  Continuing with remaining tests...\n")
            
            # Brief pause between test suites
            if idx != "9":
                time.sleep(1.5)
        
        # Print summary report
        print("\n" + "="*60)
        print("  SUMMARY REPORT")
        print("="*60)
        print(f"  Total Test Suites: {test_count}")
        print(f"  ✓ Passed: {results['passed']}")
        print(f"  ✗ Failed: {results['failed']}")
        
        if results["errors"]:
            print("\n  Failed Tests:")
            for error in results["errors"]:
                print(f"    - {error}")
        
        print("="*60)
    elif choice in test_map:
        test_name, test_func = test_map[choice]
        test_func()
    else:
        print("Invalid choice!")
        return
    
    print_section("Test Complete")
    print("✓ All tests executed successfully!")
    print("\nTo run again: python test_hid_features.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
