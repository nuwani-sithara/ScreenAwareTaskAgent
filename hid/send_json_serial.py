import serial
import sys
import json

# Get the port from command line
if len(sys.argv) < 2:
    print("Usage: python send_json_serial.py <COM port>")
    sys.exit(1)

port = sys.argv[1]
baud = 115200

try:
    with serial.Serial(port, baud, timeout=2) as ser:
        print(f"Connected to {port}!")

        # Example: send a text command
        cmd = {
            "cmd": "text",
            "value": "hi girl i am nuwani",
            "seq": 1
        }
        ser.write((json.dumps(cmd) + "\n").encode('utf-8'))

        # Wait for one response from ESP32
        response = ser.readline().decode('utf-8', errors='ignore').strip()
        if response:
            print("Response:", response)
        else:
            print("No response received (check COM port and focus).")

except serial.SerialException as e:
    print("Serial error:", e)
except KeyboardInterrupt:
    print("Exiting...")
