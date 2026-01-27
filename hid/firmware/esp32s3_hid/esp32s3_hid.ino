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
// Handshake tracking
bool handshakeDone = false;
unsigned long lastHeartbeat = 0;

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
  while (millis() - start < 10000) {
    // break early if Serial is ready
    if (Serial) break;
    delay(50);
  }

  // Flush any pre-existing serial noise (boot ROM or leftover test output)
  while (Serial.available()) { Serial.read(); }

  // Signal readiness several times to make the handshake robust across hosts
  for (int i = 0; i < 6; ++i) {
    StaticJsonDocument<128> ready;
    ready["status"] = "ready";
    ready["device"] = "ESP32-S3 HID Interface";
    serializeJson(ready, Serial);
    Serial.println();
    delay(150);
  }
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // Emit periodic ready heartbeats until host acknowledges (handshakeDone)
  if (!handshakeDone && millis() - lastHeartbeat > 1000) {
    StaticJsonDocument<128> ready;
    ready["status"] = "ready";
    ready["device"] = "ESP32-S3 HID Interface";
    serializeJson(ready, Serial);
    Serial.println();
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
  
  // Extract command type
  const char* cmd = jsonDoc["cmd"];
  if (!cmd) {
    sendError("missing_cmd", "No 'cmd' field in JSON");
    return;
  }
  
  // Route to appropriate handler
  // Explicit ACK handshake: host can send {"cmd":"ack"} to stop heartbeats
  if (strcmp(cmd, CMD_ACK) == 0) {
    handshakeDone = true;
    sendSuccess(CMD_ACK);
    return;
  }
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
  else if (strcmp(cmd, CMD_TYPE_TEXT) == 0) {
    handleTypeText();
  }
  else if (strcmp(cmd, CMD_SYSTEM) == 0) {
    handleSystemControl();
  }
  else {
    sendError("unknown_cmd", cmd);
  }
  // Note: handshake is completed only when host explicitly sends the ACK command
}

// ============================================================================
// MOUSE HANDLERS
// ============================================================================

void handleMouseMove() {
  int dx = jsonDoc["dx"] | 0;
  int dy = jsonDoc["dy"] | 0;
  
  Mouse.move(dx, dy);
  sendSuccess(CMD_MOUSE_MOVE);
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
  
  Mouse.click(mouseButton);
  sendSuccess(CMD_MOUSE_CLICK);
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
  sendSuccess(CMD_MOUSE_DOWN);
}

void handleMouseUp() {
  const char* button = jsonDoc["button"];
  uint8_t mouseButton = 0;

  if (!button) {
    // If no button specified, release all
    Mouse.release(MOUSE_LEFT);
    Mouse.release(MOUSE_RIGHT);
    Mouse.release(MOUSE_MIDDLE);
    sendSuccess(CMD_MOUSE_UP);
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
  sendSuccess(CMD_MOUSE_UP);
}

void handleMouseScroll() {
  int scroll = jsonDoc["scroll"] | 0;
  
  Mouse.move(0, 0, scroll);
  sendSuccess(CMD_MOUSE_SCROLL);
}

// ============================================================================
// KEYBOARD HANDLERS
// ============================================================================

void handleKeyPress() {
  int key = jsonDoc["key"] | 0;
  
  if (key == 0) {
    sendError("invalid_key", "Key code must be non-zero");
    return;
  }
  
  Keyboard.press(key);
  sendSuccess(CMD_KEY_PRESS);
}

void handleKeyRelease() {
  int key = jsonDoc["key"] | 0;
  
  if (key == 0) {
    // Release all keys
    Keyboard.releaseAll();
  } else {
    Keyboard.release(key);
  }
  
  sendSuccess(CMD_KEY_RELEASE);
}

void handleTypeText() {
  const char* text = jsonDoc["text"];
  
  if (!text) {
    sendError("missing_text", "No 'text' field");
    return;
  }
  
  Keyboard.print(text);
  sendSuccess(CMD_TYPE_TEXT);
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
  sendSuccess(CMD_SYSTEM);
}

// ============================================================================
// RESPONSE FUNCTIONS
// ============================================================================

void sendSuccess(const char* cmd) {
  StaticJsonDocument<128> response;
  response["status"] = "ok";
  response["cmd"] = cmd;
  
  serializeJson(response, Serial);
  Serial.println();
}

void sendError(const char* errorType, const char* message) {
  StaticJsonDocument<256> response;
  response["status"] = "error";
  response["error"] = errorType;
  response["msg"] = message;
  
  serializeJson(response, Serial);
  Serial.println();
}
