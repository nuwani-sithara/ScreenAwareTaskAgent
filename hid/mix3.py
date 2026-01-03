import serial
import time
import json
import sys

if len(sys.argv) < 2:
    print("Usage: python send_json_serial.py <COM port>")
    sys.exit(1)

port = sys.argv[1]
baud = 115200

commands = [
    {"cmd": "text", "value": "Hello from ESP32 HID!", "seq": 1},
    {"cmd": "key", "action": "tap", "key": "ENTER", "seq": 2},

    {"cmd": "text", "value": "This is a test message.", "seq": 3},
    {"cmd": "key", "action": "tap", "key": "ENTER", "seq": 4},

    {"cmd": "text", "value": "Python sending commands.", "seq": 5},
    {"cmd": "key", "action": "tap", "key": "ENTER", "seq": 6},

    {"cmd": "mouse", "x": 50, "y": 20, "seq": 7},
    {"cmd": "mouse", "x": -30, "y": 10, "seq": 8}
]

try:
    with serial.Serial(port, baud, timeout=2) as ser:
        print(f"Connected to {port}. Waiting 5 seconds before HID tasks...")
        time.sleep(5)

        for cmd in commands:
            ser.write((json.dumps(cmd) ).encode('utf-8'))
            print(f"Sent: {cmd}")

            response = ser.readline().decode('utf-8', errors='ignore').strip()
            if response:
                print(f"ESP Response: {response}")
            else:
                print("No response received.")

            time.sleep(1)  # delay between commands

except serial.SerialException as e:
    print("Serial error:", e)
except KeyboardInterrupt:
    print("Exiting...")
