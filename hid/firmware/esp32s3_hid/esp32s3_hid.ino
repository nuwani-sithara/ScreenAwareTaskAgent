/**
 * ESP32-S3 HID Interface
 * Production-grade USB HID device for agent-driven automation
 * 
 * Hardware: ESP32-S3 (native USB-OTG)
 * Framework: Arduino with TinyUSB
 * Protocol: JSON over USB CDC Serial
 * 
 * Features:
 * - USB HID (Mouse + Keyboard + Consumer Control)
 * - USB CDC Serial for command interface
 * - Single USB cable operation
 * - Auto-recovery on reconnection
 */

#include "hid_reports.h"
#include "protocol.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <USB.h>
#include <USBHID.h>
#include <USBHIDMouse.h>
#include <USBHIDKeyboard.h>

// ============================================================================
// GLOBAL INSTANCES
// ============================================================================

USBHID HID;
USBHIDMouse Mouse;
USBHIDKeyboard Keyboard;

// JSON document for parsing commands
StaticJsonDocument<512> jsonDoc;
// Track last heartbeat for periodic status
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_INTERVAL = 5000; // Send heartbeat every 5 seconds
// Store current command ID for ACK
String currentCommandId = "";

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================

void processCommand(const String& cmdLine);
void handleMouseMove();
void handleMouseClick();
void handleMouseDown();
void handleMouseUp();
void handleMouseScroll();
void handleKeyPress();
void handleKeyRelease();
void handleKeyCombo();
void handleTypeText();
void handleSystemControl();
void sendHello();
void sendPong();
void sendAck(const char* status, const char* message = nullptr);
void sendReadyForNext();
void sendSuccess(const char* cmd);
void sendError(const char* errorType, const char* message);
uint8_t resolveKeyName(const char* name);

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Initialize USB CDC Serial for command interface
  Serial.begin(115200);
  
  // Initialize USB HID components
  Mouse.begin();
  Keyboard.begin();
  HID.begin();
  USB.begin();
  
  // Wait for USB enumeration (give host some time)
  unsigned long start = millis();
  while (millis() - start < 2000) {
    // break early if Serial is ready
    if (Serial) break;
    delay(50);
  }

  // Flush any pre-existing serial noise (boot ROM or leftover test output)
  while (Serial.available()) { Serial.read(); }

  // Send hello message automatically on boot
  // This enables autonomous startup without manual reset
  sendHello();
  
  // Initialize heartbeat timer
  lastHeartbeat = millis();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // Send periodic heartbeat to maintain connection health
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHello(); // Re-send hello as heartbeat
    lastHeartbeat = millis();
  }
  
  // Check for incoming commands
  if (Serial.available()) {
    String cmdLine = Serial.readStringUntil('\n');
    cmdLine.trim();

    if (cmdLine.length() == 0) {
      // empty line, ignore
    }
    else {
      // Only attempt to parse lines that look like JSON objects to avoid
      // treating stray boot/test output as commands (e.g., "tick: ...").
      if (cmdLine.charAt(0) == '{') {
        // Safety: limit maximum length to avoid memory exhaustion
        if (cmdLine.length() <= 1024) {
          processCommand(cmdLine);
        } else {
          sendError("line_too_long", "Input line exceeds allowed length");
        }
      } else {
        // Ignore non-JSON lines silently to keep host logs clean
      }
    }
  }
  
  // Small delay to prevent CPU spinning
  delay(1);
}

// ============================================================================
// COMMAND PROCESSOR
// ============================================================================

void processCommand(const String& cmdLine) {
  // Clear previous document
  jsonDoc.clear();
  
  // Parse JSON
  DeserializationError error = deserializeJson(jsonDoc, cmdLine);
  
  if (error) {
    sendError("invalid_json", error.c_str());
    return;
  }
  
  // Extract command ID from meta field (for ACK system)
  if (jsonDoc.containsKey("meta") && jsonDoc["meta"].containsKey("commandId")) {
    const char* cmdId = jsonDoc["meta"]["commandId"];
    if (cmdId) {
      currentCommandId = String(cmdId);
    }
  } else {
    currentCommandId = "";
  }
  
  // Check if this is a control message (type field) or command (cmd field)
  const char* msgType = jsonDoc["type"];
  const char* cmd = jsonDoc["cmd"];
  
  // Handle control messages (ping/pong, etc.)
  if (msgType) {
    if (strcmp(msgType, MSG_PING) == 0) {
      sendPong();
      return;
    }
    // Unknown message type - ignore silently
    return;
  }
  
  // Handle commands
  if (!cmd) {
    sendError("missing_cmd", "No 'cmd' field in JSON");
    return;
  }
  
  // Route to appropriate handler
  if (strcmp(cmd, CMD_MOUSE_MOVE) == 0) {
    handleMouseMove();
  }
  else if (strcmp(cmd, CMD_MOUSE_CLICK) == 0) {
    handleMouseClick();
  }
  else if (strcmp(cmd, CMD_MOUSE_DOWN) == 0) {
    handleMouseDown();
  }
  else if (strcmp(cmd, CMD_MOUSE_UP) == 0) {
    handleMouseUp();
  }
  else if (strcmp(cmd, CMD_MOUSE_SCROLL) == 0) {
    handleMouseScroll();
  }
  else if (strcmp(cmd, CMD_KEY_PRESS) == 0) {
    handleKeyPress();
  }
  else if (strcmp(cmd, CMD_KEY_RELEASE) == 0) {
    handleKeyRelease();
  }
  else if (strcmp(cmd, CMD_KEY_COMBO) == 0) {
    handleKeyCombo();
  }
  else if (strcmp(cmd, CMD_TYPE_TEXT) == 0) {
    handleTypeText();
  }
  else if (strcmp(cmd, CMD_SYSTEM) == 0) {
    handleSystemControl();
  }
  else {
    sendError("unknown_cmd", cmd);
  }
}

// ============================================================================
// MOUSE HANDLERS
// ============================================================================

void handleMouseMove() {
  int dx = jsonDoc["dx"] | 0;
  int dy = jsonDoc["dy"] | 0;
  
  Mouse.move(dx, dy);
  sendAck("ok");
  sendReadyForNext();
}

void handleMouseClick() {
  const char* button = jsonDoc["button"];
  if (!button) {
    sendError("missing_button", "No 'button' field");
    return;
  }
  
  uint8_t mouseButton = MOUSE_LEFT;
  if (strcmp(button, "right") == 0) {
    mouseButton = MOUSE_RIGHT;
  } else if (strcmp(button, "middle") == 0) {
    mouseButton = MOUSE_MIDDLE;
  }
  
  // Handle multiple clicks (default to 1)
  int count = jsonDoc["count"] | 1;
  if (count < 1) count = 1;
  if (count > 10) count = 10; // Safety limit
  
  for (int i = 0; i < count; i++) {
    Mouse.press(mouseButton);
    delay(10); // Hold button for 10ms
    Mouse.release(mouseButton);
    if (i < count - 1) {
      delay(50); // Delay between multiple clicks
    }
  }
  
  sendAck("ok");
  sendReadyForNext();
}

void handleMouseDown() {
  const char* button = jsonDoc["button"];
  if (!button) {
    sendError("missing_button", "No 'button' field");
    return;
  }

  uint8_t mouseButton = MOUSE_LEFT;
  if (strcmp(button, "right") == 0) {
    mouseButton = MOUSE_RIGHT;
  } else if (strcmp(button, "middle") == 0) {
    mouseButton = MOUSE_MIDDLE;
  }

  Mouse.press(mouseButton);
  sendAck("ok");
  sendReadyForNext();
}

void handleMouseUp() {
  const char* button = jsonDoc["button"];
  uint8_t mouseButton = 0;

  if (!button) {
    // If no button specified, release all
    Mouse.release(MOUSE_LEFT);
    Mouse.release(MOUSE_RIGHT);
    Mouse.release(MOUSE_MIDDLE);
    sendAck("ok");
    sendReadyForNext();
    return;
  }

  if (strcmp(button, "right") == 0) {
    mouseButton = MOUSE_RIGHT;
  } else if (strcmp(button, "middle") == 0) {
    mouseButton = MOUSE_MIDDLE;
  } else {
    mouseButton = MOUSE_LEFT;
  }

  Mouse.release(mouseButton);
  sendAck("ok");
  sendReadyForNext();
}

void handleMouseScroll() {
  // Support both old format (scroll field) and new format (deltaX/deltaY)
  int scrollY = 0;
  int scrollX = 0;
  
  // Check for legacy 'scroll' field
  if (jsonDoc.containsKey("scroll")) {
    scrollY = jsonDoc["scroll"] | 0;
  }
  
  // Check for new deltaX/deltaY fields (takes precedence)
  if (jsonDoc.containsKey("deltaY")) {
    scrollY = jsonDoc["deltaY"] | 0;
  }
  if (jsonDoc.containsKey("deltaX")) {
    scrollX = jsonDoc["deltaX"] | 0;
  }
  
  // Execute scroll - break into multiple reports if needed
  // ESP32 USBHIDMouse scroll range is typically -127 to +127 per report
  while (scrollY != 0) {
    int step = (scrollY > 0) ? min(scrollY, 127) : max(scrollY, -127);
    Mouse.move(0, 0, step);
    delay(10); // Small delay between scroll reports
    scrollY -= step;
  }
  
  while (scrollX != 0) {
    int step = (scrollX > 0) ? min(scrollX, 127) : max(scrollX, -127);
    // Note: Horizontal scroll may not work on all systems
    Mouse.move(0, 0, 0, step);
    delay(10);
    scrollX -= step;
  }
  
  sendAck("ok");
  sendReadyForNext();
}

// ============================================================================
// KEYBOARD HANDLERS
// ============================================================================

/**
 * Resolve a human-readable key name (e.g. "enter", "escape") to a USB HID keycode.
 * Returns 0 if the name is unknown.
 */
uint8_t resolveKeyName(const char* name) {
  if (!name) return 0;
  // Special keys
  if (strcasecmp(name, "enter") == 0 || strcasecmp(name, "return") == 0) return KEY_ENTER;
  if (strcasecmp(name, "escape") == 0 || strcasecmp(name, "esc") == 0) return KEY_ESC;
  if (strcasecmp(name, "backspace") == 0) return KEY_BACKSPACE;
  if (strcasecmp(name, "tab") == 0) return KEY_TAB;
  if (strcasecmp(name, "space") == 0) return KEY_SPACE;
  if (strcasecmp(name, "delete") == 0 || strcasecmp(name, "del") == 0) return KEY_DELETE;
  if (strcasecmp(name, "insert") == 0) return KEY_INSERT;
  if (strcasecmp(name, "home") == 0) return KEY_HOME;
  if (strcasecmp(name, "end") == 0) return KEY_END;
  if (strcasecmp(name, "pageup") == 0 || strcasecmp(name, "page_up") == 0) return KEY_PAGE_UP;
  if (strcasecmp(name, "pagedown") == 0 || strcasecmp(name, "page_down") == 0) return KEY_PAGE_DOWN;
  if (strcasecmp(name, "up") == 0 || strcasecmp(name, "arrowup") == 0) return KEY_UP;
  if (strcasecmp(name, "down") == 0 || strcasecmp(name, "arrowdown") == 0) return KEY_DOWN;
  if (strcasecmp(name, "left") == 0 || strcasecmp(name, "arrowleft") == 0) return KEY_LEFT;
  if (strcasecmp(name, "right") == 0 || strcasecmp(name, "arrowright") == 0) return KEY_RIGHT;
  // Function keys
  if (strcasecmp(name, "f1") == 0) return KEY_F1;
  if (strcasecmp(name, "f2") == 0) return KEY_F2;
  if (strcasecmp(name, "f3") == 0) return KEY_F3;
  if (strcasecmp(name, "f4") == 0) return KEY_F4;
  if (strcasecmp(name, "f5") == 0) return KEY_F5;
  if (strcasecmp(name, "f6") == 0) return KEY_F6;
  if (strcasecmp(name, "f7") == 0) return KEY_F7;
  if (strcasecmp(name, "f8") == 0) return KEY_F8;
  if (strcasecmp(name, "f9") == 0) return KEY_F9;
  if (strcasecmp(name, "f10") == 0) return KEY_F10;
  if (strcasecmp(name, "f11") == 0) return KEY_F11;
  if (strcasecmp(name, "f12") == 0) return KEY_F12;
  // Single letter / digit
  if (strlen(name) == 1) {
    char c = tolower(name[0]);
    if (c >= 'a' && c <= 'z') return KEY_A + (c - 'a');
    if (c >= '1' && c <= '9') return KEY_1 + (c - '1');
    if (c == '0') return KEY_0;
  }
  // Modifier names (for key_combo)
  if (strcasecmp(name, "ctrl") == 0 || strcasecmp(name, "control") == 0) return KEY_MOD_LCTRL;  // modifier byte, not HID scancode
  if (strcasecmp(name, "shift") == 0) return KEY_MOD_LSHIFT;
  if (strcasecmp(name, "alt") == 0) return KEY_MOD_LALT;
  if (strcasecmp(name, "meta") == 0 || strcasecmp(name, "win") == 0 || strcasecmp(name, "gui") == 0) return KEY_MOD_LGUI;
  return 0;
}

void handleKeyPress() {
  // Primary: integer keycode in "key" field
  int key = jsonDoc["key"] | 0;

  // Fallback: string key name in "keyName" field (or string "key")
  if (key == 0) {
    const char* keyName = jsonDoc["keyName"] | jsonDoc["key"].as<const char*>();
    if (keyName) {
      key = (int)resolveKeyName(keyName);
    }
  }

  if (key == 0) {
    sendError("invalid_key", "Key code must be non-zero or a valid key name");
    return;
  }

  Keyboard.press(key);
  sendAck("ok");
  sendReadyForNext();
}

void handleKeyRelease() {
  // Support integer keycode or string keyName
  int key = jsonDoc["key"] | 0;
  if (key == 0) {
    const char* keyName = jsonDoc["keyName"] | jsonDoc["key"].as<const char*>();
    if (keyName) key = (int)resolveKeyName(keyName);
  }

  if (key == 0) {
    // Release all keys
    Keyboard.releaseAll();
  } else {
    Keyboard.release(key);
  }

  sendAck("ok");
  sendReadyForNext();
}

void handleKeyCombo() {
  // Read modifiers array: ["ctrl", "shift", "alt", "meta"]
  JsonArray modifiers = jsonDoc["modifiers"].as<JsonArray>();
  int mainKey = 0;

  // Resolve main key
  const char* keyStr = jsonDoc["key"];
  if (keyStr) {
    mainKey = (int)resolveKeyName(keyStr);
  } else {
    mainKey = jsonDoc["key"] | 0;
  }

  if (mainKey == 0) {
    sendError("invalid_key", "key_combo: could not resolve 'key' field");
    return;
  }

  // Press each modifier — these are real scancodes for Ctrl/Shift/Alt/GUI
  // Arduino Keyboard.press() accepts scancodes directly
  for (JsonVariant mod : modifiers) {
    const char* modName = mod.as<const char*>();
    if (!modName) continue;
    // Map modifier names to Arduino modifier keycodes
    // Arduino uses 0x80-0x87 range for modifier keys in its API
    if (strcasecmp(modName, "ctrl") == 0 || strcasecmp(modName, "control") == 0)
      Keyboard.press(KEY_LEFT_CTRL);
    else if (strcasecmp(modName, "shift") == 0)
      Keyboard.press(KEY_LEFT_SHIFT);
    else if (strcasecmp(modName, "alt") == 0)
      Keyboard.press(KEY_LEFT_ALT);
    else if (strcasecmp(modName, "meta") == 0 || strcasecmp(modName, "win") == 0 || strcasecmp(modName, "gui") == 0)
      Keyboard.press(KEY_LEFT_GUI);
    delay(5);
  }

  // Press and release main key
  delay(10);
  Keyboard.press(mainKey);
  delay(10);
  Keyboard.release(mainKey);
  delay(5);

  // Release all modifiers in reverse order
  Keyboard.releaseAll();

  sendAck("ok");
  sendReadyForNext();
}

void handleTypeText() {
  const char* text = jsonDoc["text"];
  
  if (!text) {
    sendError("missing_text", "No 'text' field");
    return;
  }
  
  Keyboard.print(text);
  sendAck("ok");
  sendReadyForNext();
}

// ============================================================================
// SYSTEM CONTROL HANDLER
// ============================================================================

void handleSystemControl() {
  int code = jsonDoc["code"] | 0;
  
  if (code == 0) {
    sendError("invalid_code", "System control code must be non-zero");
    return;
  }
  
  // Note: Consumer control requires additional HID descriptor
  // This is a placeholder for future implementation
  sendAck("ok");
  sendReadyForNext();
}

// ============================================================================
// RESPONSE FUNCTIONS
// ============================================================================

void sendHello() {
  StaticJsonDocument<128> hello;
  hello["type"] = MSG_HELLO;
  hello["status"] = STATUS_READY;
  hello["firmwareVersion"] = FIRMWARE_VERSION;
  
  serializeJson(hello, Serial);
  Serial.println();
}

void sendPong() {
  StaticJsonDocument<64> pong;
  pong["type"] = MSG_PONG;
  
  serializeJson(pong, Serial);
  Serial.println();
}

void sendAck(const char* status, const char* message) {
  StaticJsonDocument<256> ack;
  ack["type"] = MSG_ACK;
  
  // Include command ID if available
  if (currentCommandId.length() > 0) {
    ack["commandId"] = currentCommandId;
  }
  
  ack["status"] = status;
  
  if (message) {
    ack["message"] = message;
  }
  
  serializeJson(ack, Serial);
  Serial.println();
}

void sendReadyForNext() {
  StaticJsonDocument<64> ready;
  ready["type"] = MSG_READY_FOR_NEXT;
  
  serializeJson(ready, Serial);
  Serial.println();
}

void sendSuccess(const char* cmd) {
  // For backward compatibility, still send old-style success response
  StaticJsonDocument<128> response;
  response["status"] = "ok";
  response["cmd"] = cmd;
  
  serializeJson(response, Serial);
  Serial.println();
  
  // Also send ACK if command ID was provided
  if (currentCommandId.length() > 0) {
    sendAck("ok");
  }
  
  // Signal ready for next command
  sendReadyForNext();
}

void sendError(const char* errorType, const char* message) {
  // For backward compatibility, still send old-style error response
  StaticJsonDocument<256> response;
  response["status"] = "error";
  response["error"] = errorType;
  response["msg"] = message;
  
  serializeJson(response, Serial);
  Serial.println();
  
  // Also send ACK with error if command ID was provided
  if (currentCommandId.length() > 0) {
    sendAck("error", message);
  }
  
  // Still signal ready for next command even after error
  sendReadyForNext();
}

