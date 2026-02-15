# System Architecture

HID Agent Automation Platform - Complete Architecture Documentation

---

## Overview

This system enables **external agents** (LLMs, scripts, automation systems) to control a host computer **without installing software** on the host. Control is achieved through a **USB HID device** (ESP32-S3) that acts as a physical keyboard and mouse.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         AGENT LAYER                          │
│  (LLM / Planning System / External Controller)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ High-level commands
                      │ (e.g., "click button", "type text")
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    DEVICE SHADOW SERVICE                     │
│                     (Host-side service)                      │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Transport Layer                                    │    │
│  │  - Validator: Schema and bounds checking           │    │
│  │  - Sanitizer: Safety constraints                   │    │
│  │  - Normalizer: HID primitive conversion            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Motion Engine                                      │    │
│  │  - Smooth cursor interpolation                     │    │
│  │  - Human-like acceleration                         │    │
│  │  - Natural timing and jitter                       │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Command Queue                                      │    │
│  │  - Sequential execution                            │    │
│  │  - Timing management                               │    │
│  │  - Error handling                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Shadow State                                       │    │
│  │  - Connection tracking                             │    │
│  │  - Execution history                               │    │
│  │  - Statistics and monitoring                       │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Serial HID Interface                               │    │
│  │  - USB CDC Serial communication                    │    │
│  │  - Device discovery (VID/PID)                      │    │
│  │  - Auto-reconnection                               │    │
│  │  - JSON protocol handler                           │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ USB CDC Serial
                      │ JSON over newline-delimited protocol
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    ESP32-S3 FIRMWARE                         │
│                   (HID Execution Engine)                     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  USB CDC Serial Interface                           │    │
│  │  - Command reception (JSON)                        │    │
│  │  - Response transmission                           │    │
│  │  - Error reporting                                 │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Command Processor                                  │    │
│  │  - JSON parsing (ArduinoJson)                      │    │
│  │  - Command routing                                 │    │
│  │  - Parameter extraction                            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  HID Report Generators                              │    │
│  │  - Mouse reports (move, click, scroll)             │    │
│  │  - Keyboard reports (key press, text)              │    │
│  │  - Consumer control (media keys)                   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ USB HID Protocol
                      │ (Native USB-OTG)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                        HOST OPERATING SYSTEM                 │
│  (Windows / Linux / macOS)                                  │
│  - Receives HID reports as native input                     │
│  - No drivers or software installation required             │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### 1. Agent Layer

**Purpose**: High-level task planning and decision making

**Responsibilities**:
- Interpret user goals
- Plan sequences of actions
- Generate high-level commands
- Monitor execution results

**Interface**:
```typescript
// Example agent commands
await shadow.executeCommand({ cmd: 'mouse_move', dx: 100, dy: 50, smooth: true });
await shadow.executeCommand({ cmd: 'mouse_click', button: 'left' });
await shadow.executeCommand({ cmd: 'type_text', text: 'Hello World' });
```

**Does NOT**:
- Communicate directly with ESP32
- Handle HID protocol details
- Manage timing or smoothing

---

### 2. Device Shadow Service

**Purpose**: Intelligent middleware between agent and hardware

**Architecture**:

```
Agent Command
     ↓
 Validator ──→ Reject invalid commands
     ↓
 Sanitizer ──→ Clamp values to safe ranges
     ↓
 Normalizer ──→ Split into HID primitives
     ↓
Motion Engine ──→ Generate smooth movements (if needed)
     ↓
Command Queue ──→ Sequential execution with timing
     ↓
Serial HID ──→ Send to ESP32
     ↓
Shadow State ──→ Track execution and status
```

**Key Features**:
- **Validation**: Prevents malformed commands
- **Sanitization**: Ensures safety constraints
- **Normalization**: Converts to HID-compatible actions
- **Motion Smoothing**: Human-like cursor movement
- **Queue Management**: Sequential, timed execution
- **State Tracking**: Execution history and statistics
- **Auto-reconnection**: Handles USB disconnections
- **Error Recovery**: Graceful degradation

---

### 3. ESP32-S3 Firmware

**Purpose**: Pure HID execution engine

**Architecture**:

```
USB CDC Serial ──→ Receive JSON command
       ↓
   Parse JSON
       ↓
   Route to handler
       ↓
   Generate HID report
       ↓
   Send via USB HID
       ↓
   Send JSON response
```

**Constraints**:
- ❌ No complex logic
- ❌ No command queuing
- ❌ No validation (handled by shadow)
- ✅ Fast, deterministic execution
- ✅ Minimal latency
- ✅ Reliable error reporting

**Implementation Details**:
- **Framework**: Arduino + ESP32 core
- **USB Stack**: Native USB-OTG (no TinyUSB library needed)
- **Parser**: ArduinoJson
- **Interfaces**: HID (Mouse + Keyboard) + CDC Serial
- **Timing**: 1ms loop, immediate execution

---

## Data Flow Examples

### Example 1: Simple Mouse Click

```
Agent:
  ↓ executeCommand({ cmd: 'mouse_click', button: 'left' })
  
Device Shadow:
  ↓ Validate: ✓ Valid button name
  ↓ Sanitize: ✓ No changes needed
  ↓ Normalize: ✓ Single primitive
  ↓ Enqueue: Add to queue
  ↓ Execute: Send to ESP32
  
Serial Protocol:
  Host → Device: {"cmd":"mouse_click","button":"left"}\n
  
ESP32:
  ↓ Parse JSON
  ↓ Extract button
  ↓ Call Mouse.click(MOUSE_LEFT)
  ↓ Send response
  
Serial Protocol:
  Device → Host: {"status":"ok","cmd":"mouse_click"}\n
  
Device Shadow:
  ↓ Record execution
  ↓ Update statistics
  
Agent:
  ↓ Command completed
```

---

### Example 2: Large Smooth Mouse Movement

```
Agent:
  ↓ executeCommand({ cmd: 'mouse_move', dx: 500, dy: 300, smooth: true, duration: 800 })
  
Device Shadow - Validation:
  ↓ Valid numbers? ✓
  
Device Shadow - Sanitization:
  ↓ No clamping needed (will be split)
  
Device Shadow - Motion Engine:
  ↓ Generate 20 interpolated steps
  ↓ Apply ease-in-out curve
  ↓ Add small random jitter
  ↓ Calculate timing (40ms per step)
  
  Result: [
    { dx: 12, dy: 7, delay: 40 },
    { dx: 18, dy: 11, delay: 40 },
    { dx: 25, dy: 15, delay: 40 },
    ...
    { dx: 15, dy: 9, delay: 40 }
  ]
  
Device Shadow - Queue:
  ↓ Enqueue all 20 steps
  ↓ Process sequentially
  
For each step:
  Serial Protocol:
    Host → Device: {"cmd":"mouse_move","dx":12,"dy":7}\n
    Device → Host: {"status":"ok","cmd":"mouse_move"}\n
  
  Delay 40ms
  
  Next step...
  
Result:
  ✓ Smooth, human-like movement
  ✓ Natural acceleration/deceleration
  ✓ Total duration: ~800ms
```

---

## Communication Protocol

### Physical Layer
- **Interface**: USB 2.0
- **Cables**: Single USB-C cable
- **Dual Interface**:
  - USB HID (for input to OS)
  - USB CDC Serial (for commands)

### Data Link Layer
- **Format**: JSON over newline-delimited text
- **Encoding**: UTF-8
- **Baud Rate**: 115200
- **Line Ending**: `\n`

### Application Layer
See [protocol.md](protocol.md) for complete specification.

---

## State Management

### Device Shadow State

```typescript
interface ShadowState {
  connection: {
    connected: boolean;
    devicePath: string | null;
    connectedSince: number | null;
    reconnectAttempts: number;
  };
  
  execution: {
    lastCommand: any | null;
    lastCommandTime: number | null;
    lastCommandStatus: 'ok' | 'error' | null;
    lastError: string | null;
    commandsExecuted: number;
    commandsFailed: number;
  };
  
  capabilities: {
    mouse: boolean;
    keyboard: boolean;
    consumer: boolean;
  };
}
```

### Firmware State

```cpp
// Minimal state (stateless execution model)
bool isReady = false;
String lastCommand = "";
```

---

## Error Handling

### Device Shadow Errors

| Error | Handling |
|-------|----------|
| Validation failure | Reject command, return error to agent |
| Device not connected | Attempt reconnection, retry command |
| Command timeout | Mark as failed, continue with next |
| Serial port error | Reconnect and resume |

### Firmware Errors

| Error | Response |
|-------|----------|
| Invalid JSON | `{"status":"error","error":"invalid_json"}` |
| Missing parameter | `{"status":"error","error":"missing_param"}` |
| Unknown command | `{"status":"error","error":"unknown_cmd"}` |

---

## Security Model

### Trust Boundary

```
┌──────────────────┐
│  Trusted Domain  │
│  (Device Shadow) │  ← Agent must be trusted
└────────┬─────────┘
         │
         │ USB (physical security)
         │
┌────────▼─────────┐
│  ESP32-S3        │  ← No authentication
│  (HID Device)    │  ← Full OS access
└────────┬─────────┘
         │
         │ HID Protocol
         │
┌────────▼─────────┐
│  Host OS         │  ← Trusts HID implicitly
└──────────────────┘
```

### Security Constraints

⚠️ **No built-in security mechanisms**

- No authentication
- No authorization
- No rate limiting
- No input filtering beyond validation

**Mitigation**:
- Use only in controlled environments
- Physical access control
- Network isolation
- Monitored agent behavior

---

## Deployment Architecture

### Development Setup

```
┌─────────────────────────────────┐
│  Development Machine            │
│                                 │
│  ┌──────────────┐               │
│  │ Agent/LLM    │               │
│  └──────┬───────┘               │
│         │                       │
│  ┌──────▼────────────────┐     │
│  │ Device Shadow Service │     │
│  └──────┬────────────────┘     │
│         │ USB                   │
│  ┌──────▼────────┐              │
│  │ ESP32-S3      │              │
│  └───────────────┘              │
└─────────────────────────────────┘
```

### Production Setup

```
┌──────────────────┐         ┌──────────────────┐
│  Agent Server    │         │  Target Machine  │
│  (Remote)        │         │  (Controlled)    │
│                  │         │                  │
│  ┌────────────┐  │         │  ┌────────────┐  │
│  │ LLM/Planner│  │  WebSocket  │   Shadow   │  │
│  └─────┬──────┘  │◄───────►│  └─────┬──────┘  │
│        │         │         │        │ USB     │
│  ┌─────▼──────┐  │         │  ┌─────▼──────┐  │
│  │ API Server │  │         │  │ ESP32-S3   │  │
│  └────────────┘  │         │  └────────────┘  │
└──────────────────┘         └──────────────────┘
```

---

## Performance Characteristics

### Latency

| Operation | Latency |
|-----------|---------|
| Simple command (click) | 5-10ms |
| Complex command (smooth move) | 100-2000ms |
| Serial round-trip | 2-5ms |
| HID report processing | <1ms |
| USB enumeration | 1-3s |

### Throughput

| Metric | Value |
|--------|-------|
| Commands per second | 100-200 |
| Mouse movements per second | 50-100 |
| Keystrokes per second | 50-100 |
| Serial bandwidth | ~11.5 KB/s |

### Reliability

| Metric | Target |
|--------|--------|
| Command success rate | >99.9% |
| Reconnection success | >95% |
| USB stability | >24 hours continuous |

---

## Extension Points

### Adding New Commands

1. **Define command in protocol.md**
2. **Add validation in Validator**
3. **Add sanitization in Sanitizer (if needed)**
4. **Add normalization in Normalizer (if needed)**
5. **Implement handler in ESP32 firmware**
6. **Update protocol.h constants**

### Adding New HID Devices

1. **Update firmware HID descriptors**
2. **Add new report structures in hid_reports.h**
3. **Implement new command handlers**
4. **Update Device Shadow capabilities**

---

## Future Enhancements

- [ ] Consumer control (media keys) implementation
- [ ] Gamepad/joystick support
- [ ] Screen capture feedback loop
- [ ] Voice input integration
- [ ] Gesture recognition
- [ ] Multi-device coordination
- [ ] Encrypted command channel
- [ ] Rate limiting and throttling
- [ ] Command macros and scripting
- [ ] Web-based control interface

---

## References

- USB HID Specification 1.11
- ESP32-S3 Technical Reference Manual
- TinyUSB Documentation
- USB HID Usage Tables
- Human Interface Devices Design Guide

---

## Glossary

- **HID**: Human Interface Device (USB device class)
- **CDC**: Communications Device Class (USB serial)
- **VID/PID**: Vendor ID / Product ID (USB identification)
- **Shadow**: Intelligent proxy/middleware layer
- **Primitive**: Atomic, indivisible HID action
- **Report**: Single HID data packet
- **Descriptor**: USB configuration data

---

Last Updated: December 18, 2025
