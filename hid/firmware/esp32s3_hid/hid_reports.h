/**
 * HID Report Descriptors and Constants
 * 
 * This file defines HID report structures and USB constants
 * used by the ESP32-S3 HID interface.
 */

#ifndef HID_REPORTS_H
#define HID_REPORTS_H

#include <stdint.h>

// ============================================================================
// USB HID CONSTANTS
// ============================================================================

// Mouse button definitions
#define MOUSE_LEFT    0x01
#define MOUSE_RIGHT   0x02
#define MOUSE_MIDDLE  0x04
#define MOUSE_BACK    0x08
#define MOUSE_FORWARD 0x10

// ============================================================================
// HID REPORT STRUCTURES
// ============================================================================

/**
 * Standard HID Mouse Report (Boot Protocol)
 * 
 * Byte 0: Button mask (bit 0=left, bit 1=right, bit 2=middle)
 * Byte 1: X movement (-127 to 127)
 * Byte 2: Y movement (-127 to 127)
 * Byte 3: Wheel movement (-127 to 127)
 */
struct MouseReport {
  uint8_t buttons;  // Button mask
  int8_t x;         // X movement
  int8_t y;         // Y movement
  int8_t wheel;     // Wheel scroll
} __attribute__((packed));

/**
 * Standard HID Keyboard Report (Boot Protocol)
 * 
 * Byte 0: Modifier keys (Ctrl, Shift, Alt, GUI)
 * Byte 1: Reserved
 * Bytes 2-7: Up to 6 simultaneous key codes
 */
struct KeyboardReport {
  uint8_t modifiers;     // Modifier key mask
  uint8_t reserved;      // Reserved (always 0)
  uint8_t keys[6];       // Pressed key codes
} __attribute__((packed));

// ============================================================================
// HID KEYBOARD MODIFIERS (raw HID modifier byte bits)
// ============================================================================

#define KEY_MOD_LCTRL  0x01
#define KEY_MOD_LSHIFT 0x02
#define KEY_MOD_LALT   0x04
#define KEY_MOD_LGUI   0x08
#define KEY_MOD_RCTRL  0x10
#define KEY_MOD_RSHIFT 0x20
#define KEY_MOD_RALT   0x40
#define KEY_MOD_RGUI   0x80

// Arduino USBHIDKeyboard modifier key constants (used with Keyboard.press())
// These are in the 0x80–0x87 range as defined by Arduino's HID keyboard layer.
#ifndef KEY_LEFT_CTRL
#define KEY_LEFT_CTRL   0x80
#define KEY_LEFT_SHIFT  0x81
#define KEY_LEFT_ALT    0x82
#define KEY_LEFT_GUI    0x83
#define KEY_RIGHT_CTRL  0x84
#define KEY_RIGHT_SHIFT 0x85
#define KEY_RIGHT_ALT   0x86
#define KEY_RIGHT_GUI   0x87
#endif

// ============================================================================
// COMMON HID KEY CODES (USB HID Usage Tables)
// ============================================================================

#define KEY_A          0x04
#define KEY_B          0x05
#define KEY_C          0x06
#define KEY_D          0x07
#define KEY_E          0x08
#define KEY_F          0x09
#define KEY_G          0x0A
#define KEY_H          0x0B
#define KEY_I          0x0C
#define KEY_J          0x0D
#define KEY_K          0x0E
#define KEY_L          0x0F
#define KEY_M          0x10
#define KEY_N          0x11
#define KEY_O          0x12
#define KEY_P          0x13
#define KEY_Q          0x14
#define KEY_R          0x15
#define KEY_S          0x16
#define KEY_T          0x17
#define KEY_U          0x18
#define KEY_V          0x19
#define KEY_W          0x1A
#define KEY_X          0x1B
#define KEY_Y          0x1C
#define KEY_Z          0x1D

#define KEY_1          0x1E
#define KEY_2          0x1F
#define KEY_3          0x20
#define KEY_4          0x21
#define KEY_5          0x22
#define KEY_6          0x23
#define KEY_7          0x24
#define KEY_8          0x25
#define KEY_9          0x26
#define KEY_0          0x27

#define KEY_ENTER      0x28
#define KEY_ESC        0x29
#define KEY_BACKSPACE  0x2A
#define KEY_TAB        0x2B
#define KEY_SPACE      0x2C

#define KEY_F1         0x3A
#define KEY_F2         0x3B
#define KEY_F3         0x3C
#define KEY_F4         0x3D
#define KEY_F5         0x3E
#define KEY_F6         0x3F
#define KEY_F7         0x40
#define KEY_F8         0x41
#define KEY_F9         0x42
#define KEY_F10        0x43
#define KEY_F11        0x44
#define KEY_F12        0x45

#define KEY_INSERT     0x49
#define KEY_HOME       0x4A
#define KEY_PAGE_UP    0x4B
#define KEY_DELETE     0x4C
#define KEY_END        0x4D
#define KEY_PAGE_DOWN  0x4E
#define KEY_RIGHT      0x4F
#define KEY_LEFT       0x50
#define KEY_DOWN       0x51
#define KEY_UP         0x52

// ============================================================================
// CONSUMER CONTROL CODES (Media Keys)
// ============================================================================

#define CONSUMER_PLAY_PAUSE    0xCD
#define CONSUMER_STOP          0xB7
#define CONSUMER_NEXT_TRACK    0xB5
#define CONSUMER_PREV_TRACK    0xB6
#define CONSUMER_VOLUME_UP     0xE9
#define CONSUMER_VOLUME_DOWN   0xEA
#define CONSUMER_MUTE          0xE2

#endif // HID_REPORTS_H
