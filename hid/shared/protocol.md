# Serial JSON Protocol Specification

Version: 2.0.0  
Last Updated: February 21, 2026

---

## Overview

The Serial JSON Protocol defines communication between the **Device Shadow** (host service) and the **ESP32-S3 HID device** over USB CDC Serial.

All messages are **single-line JSON** terminated by newline (`\n`).

**Version 2.0.0** introduces:
- ACK-based command acknowledgment with UUID tracking
- Flow control with `readyForNext` messages
- Periodic heartbeat messages for connection health
- Enhanced error reporting

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

### Control Messages (Device → Host)

#### Hello Message
Sent by device on boot/reconnection:
```json
{
  "type": "hello",
  "status": "ready",
  "firmwareVersion": "2.0.0"
}
```

#### ACK Message
Sent after processing each command:
```json
{
  "type": "ack",
  "commandId": "<uuid>",
  "status": "ok"
}
```

Error ACK:
```json
{
  "type": "ack",
  "commandId": "<uuid>",
  "status": "error",
  "message": "<error_description>"
}
```

#### Ready For Next Message
Sent after ACK to signal readiness for next command:
```json
{
  "type": "readyForNext"
}
```

#### Ping/Pong Messages
Host sends ping:
```json
{
  "type": "ping"
}
```

Device responds with pong:
```json
{
  "cmd": "mouse_move",
  "meta": {
    "commandId": "a1b2c3d4-5678-90ab-cdef-1234567890ab"
  },
  "dx": 10,
  "dy": -5
}
```

**Response Sequence**:
```json
{"type":"ack","commandId":"a1b2c3d4-5678-90ab-cdef-1234567890ab","status":"ok"}
{"type":"readyForNext

**All commands must include a unique `commandId` in the `meta` field:**

```json
{
  "cmd": "<command_type>",
  "meta": {
    "commandId": "<uuid>"
  },
  ... command-specific parameters ...
}
```

The device echoes this `commandId` in the ACK response for correlation.

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
  "cmd": "mouse_click",
  "meta": {
    "commandId": "b2c3d4e5-6789-01bc-def0-234567890abc"
  },
  "button": "left"
}
```

**Response Sequence**:
```json
{"type":"ack","commandId":"b2c3d4e5-6789-01bc-def0-234567890abc","status":"ok"}
{"type":"readyForNext
**Example**:
```json
{"cmd":"mouse_click","button":"left"}
```

**RdeltaY": <int>,
  "deltaX": <int>  // optional, for horizontal scroll
}
```

**Parameters**:
- `deltaY`: Vertical scroll amount (positive = up, negative = down, -127 to +127)
- `deltaX`: Horizontal scroll amount (optional, positive = right, negative = left)

**Legacy Format** (still supported):
```json
{
  "cmd": "mouse_scroll",
  "scroll": <int>
}
```

**Example**:
```json
{
  "cmd": "mouse_scroll",
  "meta": {
    "commandId": "c3d4e5f6-7890-12cd-ef01-34567890abcd"
  },
  "deltaY": -3
}
```

**Response Sequence**:
```json
{"type":"ack","commandId":"c3d4e5f6-7890-12cd-ef01-34567890abcd","status":"ok"}
{"type":"readyForNext
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
{
  "cmd": "key_press",
  "meta": {
    "commandId": "d4e5f6a7-8901-23de-f012-4567890abcde"
  },
  "key": 4
}
```

**Response Sequence**:
```json
{"type":"ack","commandId":"d4e5f6a7-8901-23de-f012-4567890abcde","status":"ok"}
{"type":"readyForNext

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

*
  "cmd": "key_release",
  "meta": {
    "commandId": "e5f6a7b8-9012-34ef-0123-567890abcdef"
  },
  "key": 4
}
```

**Example** (release all):
```json
{
  "cmd": "key_release",
  "meta": {
    "commandId": "f6a7b8c9-0123-45f0-1234-67890abcdef0"
  }
}
```

**Response Sequence**:
```json
{"type":"ack","commandId":"<uuid>","status":"ok"}
{"type":"readyForNextr keycodes.

---

#### key_release

Release a key or all keys.

**Format**:
```json
{
  "cmd": "type_text",
  "meta": {
    "commandId": "a7b8c9d0-1234-56f0-1234-7890abcdef01"
  },
  "text": "Hello World"
}
```

**Response Sequence**:
```json
{"type":"ack","commandId":"a7b8c9d0-1234-56f0-1234-7890abcdef01","status":"ok"}
{"type":"readyForN
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

  "cmd": "system",
  "meta": {
    "commandId": "b8c9d0e1-2345-67f0-2345-890abcdef012"
  },
  "code": 233
}
```

**Response Sequence**:
```json
{"type":"ack","commandId":"b8c9d0e1-2345-67f0-2345-890abcdef012","status":"ok"}
{"type":"Handling

### Command Errors

When a command fails, the device returns an error ACK:

```json
{
  "type": "ack",
  "commandId": "<uuid>",
  "status": "error",
  "message": "<error_description>"
}
```

Followed by:
```json
{"type":"readyForNext"}
```

### Error Types

| Error Type       | Description                      |
|------------------|----------------------------------|
| `invalid_json`   | Malformed JSON                   |
| `missing_cmd`    | No "cmd" field in JSON           |
| `unknown_cmd`    | Unrecognized command type        |
| `missing_param`  | Required parameter not provided  |
| `invalid_param`  | Parameter value out of range     |

### Example Error Response

Request:
```json
{Connection Lifecycle

### Startup Sequence

1. **Device boots** → Firmware initializes USB HID and Serial
2. **Device sends hello**:
```json
{"type":"hello","status":"ready","firmwareVersion":"2.0.0"}
```
3. **Host waits** for hello before sending commands
4. **Device sends periodic heartbeats** every 5 seconds (hello messages)

### Command Flow

1. **Host sends command** with unique `commandId`
2. **Device processes command** and performs HID action
3. **Device sends ACK** with matching `commandId`
4. **Device sends ready500ms (host waits for ACK)
- **Retry Count**: 1 (host retries once on timeout)
- **Heartbeat Interval**: 5 seconds (device sends hello)
- **Minimum Command Interval**: Device dictates via `readyForNext`
- **Maximum In-Flight Commands**: 1 (host waits for readyForNext)

For smooth mouse movement, host should split large movements into multiple small steps with 10-20ms delays between each step
- Device sends `{"type":"hello",...}` every 5 seconds
- Host can send `{"type":"ping"}` to check connectivity
- Device responds with `{"type":"pong"}`
- If no hello/pong for 10+ seconds, assume disconnected
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
[Device boots]
Device: {"type":"hello","status":"ready","firmwareVersion":"2.0.0"}

[Host sends mouse move]
Host:   {"cmd":"mouse_move","meta":{"commandId":"uuid-1"},"dx":10,"dy":10}
Device: {"type":"ack","commandId":"uuid-1","status":"ok"}
Device: {"type":"readyForNext"}

[Host sends click]
Host:   {"cmd":"mouse_click","meta":{"commandId":"uuid-2"},"button":"left"}
Device: {"type":"ack","commandId":"uuid-2","status":"ok"}
Device: {"type":"readyForNext"}

[Host sends text]
Host:   {"cmd":"type_text","meta":{"commandId":"uuid-3"},"text":"test"}
Device: {"type":"ack","commandId":"uuid-3","status":"ok"}
Device: {"type":"readyForNext"}

[5 seconds later - periodic heartbeat]
Device: {"type":"hello","status":"ready","firmwareVersion":"2.0.0"}

[Host checks connection]
Host:   {"type":"ping"}
Device: {"type":"pong
---

## S2.0.0** (Feb 2026): ACK-based protocol with commandId tracking, flow control, heartbeat
- **tartup Sequence

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
