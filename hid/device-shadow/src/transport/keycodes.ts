/**
 * HID Keyboard Keycodes and Modifier Mappings
 * 
 * Standard USB HID keyboard usage codes
 * Reference: https://www.usb.org/sites/default/files/documents/hut1_12v2.pdf
 */

// Modifier key codes (used for key_press with modifier byte)
export const MODIFIERS = {
  CTRL: 0x01,
  SHIFT: 0x02,
  ALT: 0x04,
  META: 0x08,  // Windows/Command key
  GUI: 0x08,   // Alias for META
  RIGHT_CTRL: 0x10,
  RIGHT_SHIFT: 0x20,
  RIGHT_ALT: 0x40,
  RIGHT_META: 0x80
};

// HID keycode values for modifier keys
export const MODIFIER_KEYCODES = {
  LEFT_CTRL: 0xE0,
  LEFT_SHIFT: 0xE1,
  LEFT_ALT: 0xE2,
  LEFT_GUI: 0xE3,
  RIGHT_CTRL: 0xE4,
  RIGHT_SHIFT: 0xE5,
  RIGHT_ALT: 0xE6,
  RIGHT_GUI: 0xE7
};

// Common key HID codes
export const KEYCODES: Record<string, number> = {
  // Letters (a-z)
  'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07,
  'e': 0x08, 'f': 0x09, 'g': 0x0A, 'h': 0x0B,
  'i': 0x0C, 'j': 0x0D, 'k': 0x0E, 'l': 0x0F,
  'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13,
  'q': 0x14, 'r': 0x15, 's': 0x16, 't': 0x17,
  'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B,
  'y': 0x1C, 'z': 0x1D,
  
  // Numbers (1-9, 0)
  '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21,
  '5': 0x22, '6': 0x23, '7': 0x24, '8': 0x25,
  '9': 0x26, '0': 0x27,
  
  // Special keys
  'enter': 0x28,
  'return': 0x28,
  'escape': 0x29,
  'esc': 0x29,
  'backspace': 0x2A,
  'tab': 0x2B,
  'space': 0x2C,
  ' ': 0x2C,
  
  // Punctuation
  '-': 0x2D,
  '=': 0x2E,
  '[': 0x2F,
  ']': 0x30,
  '\\': 0x31,
  ';': 0x33,
  '\'': 0x34,
  '`': 0x35,
  ',': 0x36,
  '.': 0x37,
  '/': 0x38,
  
  // Function keys (F1-F12)
  'f1': 0x3A, 'f2': 0x3B, 'f3': 0x3C, 'f4': 0x3D,
  'f5': 0x3E, 'f6': 0x3F, 'f7': 0x40, 'f8': 0x41,
  'f9': 0x42, 'f10': 0x43, 'f11': 0x44, 'f12': 0x45,
  
  // Navigation
  'insert': 0x49,
  'home': 0x4A,
  'pageup': 0x4B,
  'pagedown': 0x4E,
  'delete': 0x4C,
  'end': 0x4D,
  'right': 0x4F,
  'left': 0x50,
  'down': 0x51,
  'up': 0x52,
  
  // Arrow keys (aliases)
  'arrowright': 0x4F,
  'arrowleft': 0x50,
  'arrowdown': 0x51,
  'arrowup': 0x52,
  
  // Numpad
  'numlock': 0x53,
  'numpad_divide': 0x54,
  'numpad_multiply': 0x55,
  'numpad_minus': 0x56,
  'numpad_plus': 0x57,
  'numpad_enter': 0x58,
  'numpad_1': 0x59,
  'numpad_2': 0x5A,
  'numpad_3': 0x5B,
  'numpad_4': 0x5C,
  'numpad_5': 0x5D,
  'numpad_6': 0x5E,
  'numpad_7': 0x5F,
  'numpad_8': 0x60,
  'numpad_9': 0x61,
  'numpad_0': 0x62,
  'numpad_decimal': 0x63,
  
  // System keys
  'capslock': 0x39,
  'printscreen': 0x46,
  'scrolllock': 0x47,
  'pause': 0x48,
  
  // Media keys (consumer control - not standard HID keyboard)
  'mute': 0xE2,
  'volumeup': 0xE9,
  'volumedown': 0xEA
};

const KEYCODE_TO_KEY: Record<number, string> = Object.entries(KEYCODES)
  .reduce((acc, [key, code]) => {
    if (acc[code] === undefined) {
      acc[code] = key;
    }
    return acc;
  }, {} as Record<number, string>);

const MODIFIER_KEYCODE_TO_KEY: Record<number, string> = {
  [MODIFIER_KEYCODES.LEFT_CTRL]: 'control',
  [MODIFIER_KEYCODES.LEFT_SHIFT]: 'shift',
  [MODIFIER_KEYCODES.LEFT_ALT]: 'alt',
  [MODIFIER_KEYCODES.LEFT_GUI]: 'command',
  [MODIFIER_KEYCODES.RIGHT_CTRL]: 'control',
  [MODIFIER_KEYCODES.RIGHT_SHIFT]: 'shift',
  [MODIFIER_KEYCODES.RIGHT_ALT]: 'alt',
  [MODIFIER_KEYCODES.RIGHT_GUI]: 'command'
};

/**
 * Map modifier name to HID keycode
 */
export function modifierNameToKeycode(modifierName: string): number {
  const normalized = modifierName.toLowerCase();
  
  switch (normalized) {
    case 'ctrl':
    case 'control':
      return MODIFIER_KEYCODES.LEFT_CTRL;
    case 'shift':
      return MODIFIER_KEYCODES.LEFT_SHIFT;
    case 'alt':
    case 'option':
      return MODIFIER_KEYCODES.LEFT_ALT;
    case 'meta':
    case 'win':
    case 'windows':
    case 'cmd':
    case 'command':
    case 'gui':
      return MODIFIER_KEYCODES.LEFT_GUI;
    case 'rightctrl':
    case 'rightcontrol':
      return MODIFIER_KEYCODES.RIGHT_CTRL;
    case 'rightshift':
      return MODIFIER_KEYCODES.RIGHT_SHIFT;
    case 'rightalt':
      return MODIFIER_KEYCODES.RIGHT_ALT;
    case 'rightmeta':
    case 'rightwin':
    case 'rightcmd':
    case 'rightgui':
      return MODIFIER_KEYCODES.RIGHT_GUI;
    default:
      throw new Error(`Unknown modifier: ${modifierName}`);
  }
}

/**
 * Map key string to HID keycode
 */
export function keyToKeycode(key: string): number {
  const normalized = key.toLowerCase();
  
  if (KEYCODES[normalized] !== undefined) {
    return KEYCODES[normalized];
  }
  
  throw new Error(`Unknown key: ${key}`);
}

/**
 * Map HID keycode to key string
 */
export function keycodeToKey(keycode: number): string | null {
  if (MODIFIER_KEYCODE_TO_KEY[keycode] !== undefined) {
    return MODIFIER_KEYCODE_TO_KEY[keycode];
  }

  if (KEYCODE_TO_KEY[keycode] !== undefined) {
    return KEYCODE_TO_KEY[keycode];
  }

  return null;
}

/**
 * Check if a string is a valid modifier name
 */
export function isValidModifier(name: string): boolean {
  const normalized = name.toLowerCase();
  const validModifiers = [
    'ctrl', 'control', 'shift', 'alt', 'option',
    'meta', 'win', 'windows', 'cmd', 'command', 'gui',
    'rightctrl', 'rightcontrol', 'rightshift', 'rightalt',
    'rightmeta', 'rightwin', 'rightcmd', 'rightgui'
  ];
  return validModifiers.includes(normalized);
}

/**
 * Check if a string is a valid key name
 */
export function isValidKey(name: string): boolean {
  const normalized = name.toLowerCase();
  return KEYCODES[normalized] !== undefined;
}
