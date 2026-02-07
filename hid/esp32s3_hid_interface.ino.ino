#include <Arduino.h>
#include <USB.h>
#include <USBHIDKeyboard.h>
#include <USBHIDMouse.h>
#include <ArduinoJson.h>

// HID devices
USBHIDKeyboard Keyboard;
USBHIDMouse Mouse;
USBHID HID;

void setup() {
  Serial.begin(115200);
  HID.begin();
  Keyboard.begin();
  Mouse.begin();
  USB.begin();
  
  delay(1000); // allow host to detect HID
  Serial.println("{\"status\":\"ready\"}");
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, line) != DeserializationError::Ok) {
      Serial.println("{\"status\":\"error\",\"msg\":\"Invalid JSON\"}");
      return;
    }

    const char* cmd = doc["cmd"];

    // ===== Text Command =====
    if (strcmp(cmd, "text") == 0) {
      const char* text = doc["value"];
      Keyboard.print(text);
    }

    // ===== Key Command =====
    else if (strcmp(cmd, "key") == 0) {
      const char* action = doc["action"];
      const char* keyname = doc["key"];

      uint8_t keycode = 0;
      if (strcmp(keyname, "ENTER") == 0) keycode = KEY_RETURN;
      else if (strcmp(keyname, "TAB") == 0) keycode = KEY_TAB;
      else if (strcmp(keyname, "ESC") == 0) keycode = KEY_ESC;
      // Add more key constants as needed

      if (keycode != 0) {
        if (strcmp(action, "tap") == 0) {
          Keyboard.press(keycode);
          delay(20);
          Keyboard.release(keycode);
        } else if (strcmp(action, "down") == 0) {
          Keyboard.press(keycode);
        } else if (strcmp(action, "up") == 0) {
          Keyboard.release(keycode);
        }
      }
    }

    // ===== Mouse Command =====
    else if (strcmp(cmd, "mouse") == 0) {
      int x = doc["x"] | 0;
      int y = doc["y"] | 0;
      Mouse.move(x, y);
    }

    // Send ACK
    Serial.print("{\"seq\":");
    Serial.print(doc["seq"].as<int>());
    Serial.println(",\"status\":\"ok\"}");
  }
}
