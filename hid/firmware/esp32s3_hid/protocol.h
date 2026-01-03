/**
 * Serial JSON Protocol Definitions
 * 
 * This file defines the command protocol used between
 * the Device Shadow service and the ESP32-S3 HID interface.
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

// ============================================================================
// COMMAND TYPES
// ============================================================================

// Mouse commands
#define CMD_MOUSE_MOVE   "mouse_move"
#define CMD_MOUSE_CLICK  "mouse_click"
#define CMD_MOUSE_SCROLL "mouse_scroll"

// Keyboard commands
#define CMD_KEY_PRESS    "key_press"
#define CMD_KEY_RELEASE  "key_release"
#define CMD_TYPE_TEXT    "type_text"

// System commands
#define CMD_SYSTEM       "system"
#define CMD_PING         "ping"
// Handshake ACK from host
#define CMD_ACK          "ack"

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
 * All commands are sent as single-line JSON terminated by \n
 * All responses are single-line JSON terminated by \n
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
 * System Control:
 *   { "cmd": "system", "code": <int> }
 * 
 * Ping:
 *   { "cmd": "ping" }
 * 
 * RESPONSE FORMATS:
 * 
 * Success:
 *   { "status": "ok", "cmd": "<command_type>" }
 * 
 * Error:
 *   { "status": "error", "error": "<error_type>", "msg": "<message>" }
 * 
 * Ready (on startup):
 *   { "status": "ready", "device": "ESP32-S3 HID Interface" }
 */

#endif // PROTOCOL_H
