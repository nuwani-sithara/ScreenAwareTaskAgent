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

# Array of commands (text + Enter key + mouse moves)
commands = [
    {"cmd": "text", "value": "Hello from ESP32 HID!", "seq": 1},
    {"cmd": "key", "action": "down", "keycode": 40, "seq": 2},  # Enter key down
    {"cmd": "key", "action": "up", "keycode": 40, "seq": 3},    # Enter key up

    {"cmd": "text", "value": "This is a test message.", "seq": 4},
    {"cmd": "key", "action": "down", "keycode": 40, "seq": 5},
    {"cmd": "key", "action": "up", "keycode": 40, "seq": 6},

    {"cmd": "text", "value": "Python sending commands.", "seq": 7},
    {"cmd": "key", "action": "down", "keycode": 40, "seq": 8},
    {"cmd": "key", "action": "up", "keycode": 40, "seq": 9},

    {"cmd": "mouse", "x": 50, "y": 20, "seq": 10},  # move mouse
    {"cmd": "mouse", "x": -30, "y": 10, "seq": 11}  # move mouse again
]

try:
    with serial.Serial(port, baud, timeout=2) as ser:
        print(f"Connected to {port}! Waiting 3 seconds before starting HID tasks...")
        time.sleep(5)  # wait before starting HID task

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
            time.sleep(1)  # 1 second delay between commands

except serial.SerialException as e:
    print("Serial error:", e)
except KeyboardInterrupt:
    print("Exiting...")
