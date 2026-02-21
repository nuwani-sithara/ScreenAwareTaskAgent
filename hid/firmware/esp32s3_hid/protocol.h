/**
 * Serial JSON Protocol Definitions
 * 
 * This file defines the command protocol used between
 * the Device Shadow service and the ESP32-S3 HID interface.
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

// ============================================================================
// FIRMWARE VERSION
// ============================================================================

#define FIRMWARE_VERSION "2.0.0"

// ============================================================================
// MESSAGE TYPES (for handshake/control messages)
// ============================================================================

#define MSG_HELLO        "hello"
#define MSG_PING         "ping"
#define MSG_PONG         "pong"
#define MSG_ACK          "ack"
#define MSG_READY_FOR_NEXT "readyForNext"

// ============================================================================
// COMMAND TYPES
// ============================================================================

// Mouse commands
#define CMD_MOUSE_MOVE   "mouse_move"
#define CMD_MOUSE_CLICK  "mouse_click"
#define CMD_MOUSE_SCROLL "mouse_scroll"
#define CMD_MOUSE_DRAG   "mouse_drag"
// Mouse button press/release (for drag operations)
#define CMD_MOUSE_DOWN   "mouse_down"
#define CMD_MOUSE_UP     "mouse_up"

// Keyboard commands
#define CMD_KEY_PRESS    "key_press"
#define CMD_KEY_RELEASE  "key_release"
#define CMD_TYPE_TEXT    "type_text"
#define CMD_KEY_COMBO    "key_combo"

// System commands
#define CMD_SYSTEM       "system"

// ============================================================================
// RESPONSE STATUS CODES
// ============================================================================

#define STATUS_OK        "ok"
#define STATUS_ERROR     "error"
#define STATUS_READY     "ready"

// ============================================================================
// ERROR TYPES
// ============================================================================

#define ERROR_INVALID_JSON    "invalid_json"
#define ERROR_MISSING_CMD     "missing_cmd"
#define ERROR_UNKNOWN_CMD     "unknown_cmd"
#define ERROR_MISSING_PARAM   "missing_param"
#define ERROR_INVALID_PARAM   "invalid_param"

// ============================================================================
// PROTOCOL SPECIFICATION
// ============================================================================

/**
 * All messages are sent as single-line JSON terminated by \n
 * 
 * HANDSHAKE MESSAGES:
 * 
 * Hello (sent by device on boot):
 *   { "type": "hello", "status": "ready", "firmwareVersion": "2.0.0" }
 * 
 * Ping (sent by host to check connectivity):
 *   { "type": "ping" }
 * 
 * Pong (sent by device in response to ping):
 *   { "type": "pong" }
 * 
 * ACK (sent by device after executing a command):
 *   { "type": "ack", "commandId": "<uuid>", "status": "ok" }
 * All commands must include a "meta" field with commandId:
 *   { "cmd": "<command>", "meta": { "commandId": "<uuid>" }, ... }
 * 
 *   { "type": "ack", "commandId": "<uuid>", "status": "error", "message": "<error>" }
 * 
 * Ready for Next (sent by device when ready to accept next command):
 *   { "type": "readyForNext" }
 * 
 * COMMAND FORMATS:
 * 
 * Mouse Move:
 *   { "cmd": "mouse_move", "dx": <int>, "dy": <int> }
 * 
 * Mouse Click:
 *   { "cmd": "mouse_click", "button": "left"|"right"|"middle" }
 * 
 * Mouse Scroll:
 *   { "cmd": "mouse_scroll", "scroll": <int> }
 *   { "cmd": "mouse_scroll", "deltaY": <int> }
 *   { "cmd": "mouse_scroll", "deltaX": <int>, "deltaY": <int> }
 * 
 * Mouse Drag:
 *   { "cmd": "mouse_drag", "dx": <int>, "dy": <int>, "button": "left"|"right"|"middle", "duration": <int> }
 * 
 * Mouse Press:
 *   { "cmd": "mouse_down", "button": "left"|"right"|"middle" }
 * 
 * Mouse Release:
 *   { "cmd": "mouse_up", "button": "left"|"right"|"middle" }
 *   { "cmd": "mouse_up" }  // Release all buttons
 * 
 * Key Press:
 *   { "cmd": "key_press", "key": <keycode> }
 * 
 * Key Release:
 *   { "cmd": "key_release", "key": <keycode> }
 *   { "cmd": "key_release" }  // Release all keys
 * 
 * Type Text:
 *   { "cmd": "type_text", "text": "<string>" }
 * 
 * Key Combination:
 *   { "cmd": "key_combo", "modifiers": ["ctrl", "shift", "alt", "meta"], "key": "<char>" }
 *   { "cmd": "key_combo", "modifiers": ["ctrl"], "key": "c" }
 * 
 * System Control:
 *   { "cmd": "system", "code": <int> }
 * 
 * RESPONSE FORMATS:
 * 
 * Success:
 *   { "status": "ok", "cmd": "<command_type>" }
 * 
 * Error:
 *   { "status": "error", "error": "<error_type>", "msg": "<message>" }
 */

#endif // PROTOCOL_H
