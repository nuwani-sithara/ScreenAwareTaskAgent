import serial
import time
import json
import sys

# Get COM port from command line
if len(sys.argv) < 2:
    print("Usage: python send_json_serial.py <COM port>")
    sys.exit(1)

port = sys.argv[1]
baud = 115200

# Array of commands (mixed types)
commands = [
    {"cmd": "text", "value": "Hello from ESP32 HID!", "seq": 1},
    {"cmd": "key", "action": "tap", "keycode": 40, "seq": 2},  # Enter key
    {"cmd": "text", "value": "This is a test message.", "seq": 3},
    {"cmd": "mouse", "x": 50, "y": 20, "seq": 4},             # move mouse
    {"cmd": "text", "value": "Python sending commands.", "seq": 5},
    {"cmd": "key", "action": "tap", "keycode": 40, "seq": 6},  # Enter key
    {"cmd": "mouse", "x": -30, "y": 10, "seq": 7}             # move mouse again
]

try:
    with serial.Serial(port, baud, timeout=2) as ser:
        print(f"Connected to {port}! Waiting 3 seconds before starting HID tasks...")
        time.sleep(3)  # wait before starting HID task

        for cmd in commands:
            # Send JSON command
            ser.write((json.dumps(cmd) + "\n").encode('utf-8'))
            print(f"Sent: {cmd}")

            # Read response
            response = ser.readline().decode('utf-8', errors='ignore').strip()
            if response:
                print(f"ESP Response: {response}")
            else:
                print("No response received.")

            # Delay between commands
            time.sleep(1)  # 1 second delay, can be increased if needed

except serial.SerialException as e:
    print("Serial error:", e)
except KeyboardInterrupt:
    print("Exiting...")
