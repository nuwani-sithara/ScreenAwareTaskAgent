# ESP32-S3 HID Firmware

Production-grade USB HID firmware for agent-driven automation.

## Hardware Requirements

- **Board**: ESP32-S3 DevKit (with native USB-OTG)
- **Connection**: Single USB-C cable to host
- **Interfaces**: 
  - USB HID (Mouse + Keyboard)
  - USB CDC Serial (Command interface)

## Features

- ✅ Native USB HID device (no drivers needed)
- ✅ JSON command protocol
- ✅ Mouse control (move, click, scroll)
- ✅ Keyboard control (key press, text typing)
- ✅ Single USB cable operation
- ✅ Auto-recovery on reconnection
- ✅ Arduino IDE compatible

## Arduino IDE Setup

### 1. Install ESP32 Board Support

1. Open Arduino IDE
2. Go to **File → Preferences**
3. Add to "Additional Board Manager URLs":
   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```
4. Go to **Tools → Board → Boards Manager**
5. Search for "esp32"
6. Install "esp32" by Espressif Systems (version 2.0.11 or later)

### 2. Install Required Libraries

Go to **Tools → Manage Libraries** and install:

- **ArduinoJson** (by Benoit Blanchon, version 6.x)

### 3. Board Configuration

- **Board**: "ESP32S3 Dev Module"
- **USB Mode**: "Hardware CDC and JTAG"
- **USB CDC On Boot**: "Enabled"
- **Upload Mode**: "UART0 / Hardware CDC"
- **Port**: Select your ESP32-S3 COM port

## Compilation

1. Open `esp32s3_hid.ino` in Arduino IDE
2. Select the correct board and port
3. Click **Verify** to compile
4. Click **Upload** to flash

**Expected Output**: No errors, successful upload

## Testing

### 1. Open Serial Monitor

- **Baud Rate**: 115200
- **Line Ending**: Newline

### 2. Expected Startup Message

```json
{"status":"ready","device":"ESP32-S3 HID Interface"}
```

### 3. Test Commands

Send these JSON commands (one per line):

**Move mouse right and down:**
```json
{"cmd":"mouse_move","dx":10,"dy":10}
```

**Left click:**
```json
{"cmd":"mouse_click","button":"left"}
```

**Type text:**
```json
{"cmd":"type_text","text":"Hello World"}
```

**Scroll up:**
```json
{"cmd":"mouse_scroll","scroll":3}
```

## Protocol Reference

See [protocol.h](protocol.h) for complete command specifications.

## File Structure

```
esp32s3_hid/
├── esp32s3_hid.ino    # Main firmware (command processor)
├── hid_reports.h       # HID descriptors and constants
├── protocol.h          # JSON protocol definitions
└── README.md           # This file
```

## Troubleshooting

### Device Not Recognized

- Ensure "USB CDC On Boot" is enabled
- Try a different USB cable
- Press and hold BOOT button, then press RESET

### Compilation Errors

- Verify ESP32 board package version ≥ 2.0.11
- Ensure ArduinoJson library is installed
- Check board selection matches your hardware

### No Serial Output

- Verify correct COM port selection
- Check baud rate is 115200
- Ensure USB cable supports data (not charge-only)

## Integration

This firmware is designed to work with the **Device Shadow** service running on the host machine. The Device Shadow handles:

- Command validation and normalization
- Motion smoothing for realistic cursor movement
- Command queuing and execution tracking
- Error recovery and reconnection logic

For host-side integration, see `device-shadow/` directory.

## Security Considerations

⚠️ This device acts as a **full HID controller** with unrestricted input access. Use only in controlled environments:

- Research and automation systems
- Accessibility applications
- Testing and QA environments

**Do not** use this for unauthorized access or malicious purposes.

## License

Research and educational use only.

## Quick Flash Helper

If you prefer command-line flashing, a PowerShell helper `flash_firmware.ps1` is included in this folder. It uses `arduino-cli` to compile and upload the sketch. Example:

- Install `arduino-cli` and the ESP32 core as described in the Arduino docs.
- Run in PowerShell: `.\flash_firmware.ps1 -Port COM3`

After upload, open serial monitor at 115200 and verify the device prints the readiness JSON. If you see non-JSON output such as `tick:` lines, re-flash the production firmware.
