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

# Array of text commands to send
commands = [
    "Hello from ESP32 HID!",
    "This is a test message.",
    "Sending multiple commands.",
    "Python controlling HID.",
    "Last message in array."
]

try:
    with serial.Serial(port, baud, timeout=2) as ser:
        print(f"Connected to {port}! Waiting 3 seconds before starting...")
        time.sleep(3)  # wait before starting HID task

        seq = 1
        for text in commands:
            cmd = {
                "cmd": "text",
                "value": text,
                "seq": seq
            }
            # Send JSON command
            ser.write((json.dumps(cmd) + "\n").encode('utf-8'))
            print(f"Sent: {cmd}")

            # Read response
            response = ser.readline().decode('utf-8', errors='ignore').strip()
            if response:
                print(f"ESP Response: {response}")
            else:
                print("No response received.")

            seq += 1
            time.sleep(0.5)  # optional small delay between commands

except serial.SerialException as e:
    print("Serial error:", e)
except KeyboardInterrupt:
    print("Exiting...")
