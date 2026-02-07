# Serial JSON Protocol Specification

Version: 1.0  
Last Updated: December 18, 2025

---

## Overview

The Serial JSON Protocol defines communication between the **Device Shadow** (host service) and the **ESP32-S3 HID device** over USB CDC Serial.

All messages are **single-line JSON** terminated by newline (`\n`).

---

## Connection Parameters

- **Baud Rate**: 115200
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1
- **Flow Control**: None
- **Encoding**: UTF-8

---

## Message Format

### Device → Host (Responses)

All responses follow this structure:

```json
{
  "status": "ok" | "error" | "ready",
  "cmd": "<command_type>",
  "error": "<error_type>",
  "msg": "<error_message>",
  "device": "<device_info>"
}
```

### Host → Device (Commands)

All commands follow this structure:

```json
{
  "cmd": "<command_type>",
  ... additional parameters ...
}
```

---

## Command Reference

### Mouse Commands

#### mouse_move

Move mouse cursor relative to current position.

**Format**:
```json
{
  "cmd": "mouse_move",
  "dx": <int>,
  "dy": <int>
}
```

**Parameters**:
- `dx`: X-axis movement (pixels, -127 to +127 per report)
- `dy`: Y-axis movement (pixels, -127 to +127 per report)

**Example**:
```json
{"cmd":"mouse_move","dx":10,"dy":-5}
```

**Response**:
```json
{"status":"ok","cmd":"mouse_move"}
```

---

#### mouse_click

Click a mouse button.

**Format**:
```json
{
  "cmd": "mouse_click",
  "button": "left" | "right" | "middle"
}
```

**Parameters**:
- `button`: Which button to click

**Example**:
```json
{"cmd":"mouse_click","button":"left"}
```

**Response**:
```json
{"status":"ok","cmd":"mouse_click"}
```

---

#### mouse_scroll

Scroll mouse wheel.

**Format**:
```json
{
  "cmd": "mouse_scroll",
  "scroll": <int>
}
```

**Parameters**:
- `scroll`: Scroll amount (positive = up, negative = down, -10 to +10)

**Example**:
```json
{"cmd":"mouse_scroll","scroll":3}
```

**Response**:
```json
{"status":"ok","cmd":"mouse_scroll"}
```

---

### Keyboard Commands

#### key_press

Press a key (without releasing).

**Format**:
```json
{
  "cmd": "key_press",
  "key": <keycode>
}
```

**Parameters**:
- `key`: USB HID keycode (0-255)

**Example**:
```json
{"cmd":"key_press","key":4}
```

**Response**:
```json
{"status":"ok","cmd":"key_press"}
```

**Note**: See HID Usage Tables for keycodes.

---

#### key_release

Release a key or all keys.

**Format**:
```json
{
  "cmd": "key_release",
  "key": <keycode>
}
```

**Parameters**:
- `key`: USB HID keycode (optional, if omitted releases all keys)

**Example** (release specific key):
```json
{"cmd":"key_release","key":4}
```

**Example** (release all):
```json
{"cmd":"key_release"}
```

**Response**:
```json
{"status":"ok","cmd":"key_release"}
```

---

#### type_text

Type ASCII text string.

**Format**:
```json
{
  "cmd": "type_text",
  "text": "<string>"
}
```

**Parameters**:
- `text`: ASCII text to type (max 1000 characters)

**Example**:
```json
{"cmd":"type_text","text":"Hello World"}
```

**Response**:
```json
{"status":"ok","cmd":"type_text"}
```

---

### System Commands

#### system

Send system/consumer control code.

**Format**:
```json
{
  "cmd": "system",
  "code": <int>
}
```

**Parameters**:
- `code`: Consumer control code (0-65535)

**Example** (volume up):
```json
{"cmd":"system","code":233}
```

**Response**:
```json
{"status":"ok","cmd":"system"}
```

**Note**: Consumer control not yet fully implemented in firmware.

---

## Error Responses

When a command fails, the device returns:

```json
{
  "status": "error",
  "error": "<error_type>",
  "msg": "<human_readable_message>"
}
```

### Error Types

| Error Type       | Description                      |
|------------------|----------------------------------|
| `invalid_json`   | Malformed JSON                   |
| `missing_cmd`    | No "cmd" field in JSON           |
| `unknown_cmd`    | Unrecognized command type        |
| `missing_param`  | Required parameter not provided  |
| `invalid_param`  | Parameter value out of range     |

### Example Error

```json
{
  "status": "error",
  "error": "missing_param",
  "msg": "No 'button' field"
}
```

---

## Startup Sequence

On boot or USB reconnection, device sends:

```json
{
  "status": "ready",
  "device": "ESP32-S3 HID Interface"
}
```

Host must wait for this message before sending commands.

---

## Timing Constraints

- **Command Timeout**: 2 seconds
- **Minimum Command Interval**: 1ms
- **Maximum Queue Depth**: 100 commands

For smooth mouse movement, host should split large movements into multiple small steps with 10-20ms delays.

---

## HID Keycode Reference

Common USB HID keycodes:

| Key       | Code | Key       | Code |
|-----------|------|-----------|------|
| A-Z       | 0x04-0x1D | 0-9  | 0x1E-0x27 |
| Enter     | 0x28 | Escape    | 0x29 |
| Backspace | 0x2A | Tab       | 0x2B |
| Space     | 0x2C | F1-F12    | 0x3A-0x45 |
| Right     | 0x4F | Left      | 0x50 |
| Down      | 0x51 | Up        | 0x52 |

Full reference: [USB HID Usage Tables](https://www.usb.org/sites/default/files/documents/hut1_12v2.pdf)

---

## Best Practices

1. **Always validate JSON** before sending
2. **Wait for response** before sending next command
3. **Handle errors gracefully** and retry if needed
4. **Split large movements** into smaller steps
5. **Add delays** between commands for human-like timing
6. **Monitor device status** and reconnect if needed

---

## Example Session

```
Device: {"status":"ready","device":"ESP32-S3 HID Interface"}
Host:   {"cmd":"mouse_move","dx":10,"dy":10}
Device: {"status":"ok","cmd":"mouse_move"}
Host:   {"cmd":"mouse_click","button":"left"}
Device: {"status":"ok","cmd":"mouse_click"}
Host:   {"cmd":"type_text","text":"test"}
Device: {"status":"ok","cmd":"type_text"}
```

---

## Security Considerations

⚠️ **This protocol provides unrestricted HID access**

- No authentication
- No authorization
- No rate limiting (firmware-level)
- Full keyboard and mouse control

Use only in trusted, controlled environments.

---

## Version History

- **1.0** (Dec 2025): Initial protocol specification

---

## References

- USB HID Specification 1.11
- USB HID Usage Tables 1.12
- ESP32-S3 TinyUSB Documentation
- ArduinoJson Library Documentation
