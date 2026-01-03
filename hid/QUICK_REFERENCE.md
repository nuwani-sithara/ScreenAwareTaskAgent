# Quick Reference Card

## 📦 Installation

```bash
# Install Device Shadow dependencies
cd device-shadow
npm install

# Build TypeScript
npm run build
```

## ⚡ Quick Test

```bash
# Run basic example
node dist/example.js basic

# Run simple test
node dist/example.js simple

# Run advanced example
node dist/example.js advanced
```

## 🔌 Firmware Commands (Serial Monitor)

Test directly via Serial Monitor (115200 baud):

```json
{"cmd":"mouse_move","dx":10,"dy":10}
{"cmd":"mouse_click","button":"left"}
{"cmd":"type_text","text":"test"}
{"cmd":"mouse_scroll","scroll":3}
{"cmd":"key_press","key":4}
{"cmd":"key_release","key":4}
```

## 💻 Device Shadow API

```typescript
import DeviceShadow from './device-shadow/src/index';

const shadow = new DeviceShadow();

// Connect
await shadow.connect();

// Mouse move (smooth)
await shadow.executeCommand({
  cmd: 'mouse_move',
  dx: 200,
  dy: 100,
  smooth: true,
  duration: 500
});

// Click
await shadow.executeCommand({
  cmd: 'mouse_click',
  button: 'left'  // or 'right', 'middle'
});

// Type text
await shadow.executeCommand({
  cmd: 'type_text',
  text: 'Hello World'
});

// Scroll
await shadow.executeCommand({
  cmd: 'mouse_scroll',
  scroll: 3  // positive = up, negative = down
});

// Key press
await shadow.executeCommand({
  cmd: 'key_press',
  key: 0x04  // HID keycode
});

// Key release
await shadow.executeCommand({
  cmd: 'key_release',
  key: 0x04
});

// Statistics
console.log(shadow.getStats());

// Disconnect
await shadow.disconnect();
```

## 🔑 Common HID Keycodes

```typescript
// Letters
A = 0x04, B = 0x05, ..., Z = 0x1D

// Numbers
1 = 0x1E, 2 = 0x1F, ..., 0 = 0x27

// Special keys
ENTER = 0x28
ESCAPE = 0x29
BACKSPACE = 0x2A
TAB = 0x2B
SPACE = 0x2C

// Function keys
F1 = 0x3A, F2 = 0x3B, ..., F12 = 0x45

// Arrows
RIGHT = 0x4F
LEFT = 0x50
DOWN = 0x51
UP = 0x52

// Modifiers
LEFT_CTRL = 0xE0
LEFT_SHIFT = 0xE1
LEFT_ALT = 0xE2
LEFT_WIN = 0xE3
```

## 🐛 Troubleshooting

### Device not found
```bash
# Check if ESP32 is connected
ls /dev/ttyUSB* # Linux
ls /dev/tty.* # macOS
# Check Device Manager on Windows
```

### Firmware won't compile
- Verify ESP32 board package ≥ v2.0.11
- Install ArduinoJson library (v6.x)
- Select: ESP32S3 Dev Module
- Enable: USB CDC On Boot

### Commands not working
- Check Serial Monitor for errors
- Verify baud rate: 115200
- Wait for ready message
- Check JSON syntax

### TypeScript errors
```bash
cd device-shadow
npm install --save-dev @types/node
npm run build
```

## 📁 File Locations

| Component | Path |
|-----------|------|
| Firmware | `firmware/esp32s3_hid/esp32s3_hid.ino` |
| Main Service | `device-shadow/src/index.ts` |
| Examples | `device-shadow/example.ts` |
| Protocol Spec | `shared/protocol.md` |
| Architecture | `shared/architecture.md` |

## 🔗 Quick Links

- [Master README](README.md)
- [Firmware Setup](firmware/esp32s3_hid/README.md)
- [Device Shadow Setup](device-shadow/README.md)
- [Protocol Spec](shared/protocol.md)
- [Architecture](shared/architecture.md)

## ⚙️ Arduino IDE Board Settings

```
Board: ESP32S3 Dev Module
USB Mode: Hardware CDC and JTAG
USB CDC On Boot: Enabled
Upload Mode: UART0 / Hardware CDC
Port: [Select your ESP32-S3 port]
```

## 📡 USB Interfaces

After flashing, ESP32-S3 exposes:

1. **USB HID** - Mouse + Keyboard (no drivers needed)
2. **USB CDC Serial** - Command interface (port for Device Shadow)

Use CDC Serial port for Device Shadow connection.

## ✅ System Check

```bash
# 1. Flash firmware
# 2. Open Serial Monitor
# Expected: {"status":"ready","device":"ESP32-S3 HID Interface"}

# 3. Test command
# Send: {"cmd":"mouse_move","dx":5,"dy":5}
# Expected: {"status":"ok","cmd":"mouse_move"}

# 4. Run Device Shadow example
cd device-shadow
node dist/example.js simple

# Expected: Mouse moves in square pattern
```

---

**For detailed information, see README.md**
