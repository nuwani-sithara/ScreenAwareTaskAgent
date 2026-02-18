/**
 * Protocol Constants
 * 
 * Shared constants for HID protocol
 */

// ============================================================================
// TIMING CONSTANTS
// ============================================================================

export const TIMING = {
  // Command timing
  COMMAND_TIMEOUT: 500,           // ms - Timeout for ACK response
  COMMAND_RETRY_MAX: 1,            // Max number of retries
  KEY_COMBO_DELAY: 5,              // ms - Delay between key press/release in combos
  KEY_COMBO_MAIN_DELAY: 10,        // ms - Delay for main key press
  MOUSE_DRAG_BUTTON_DELAY: 10,     // ms - Delay after button press in drag
  MOUSE_DRAG_RELEASE_DELAY: 20,    // ms - Delay before button release in drag
  
  // Connection timing
  HELLO_TIMEOUT: 3000,             // ms - Timeout for hello message
  PONG_TIMEOUT: 2000,              // ms - Timeout for pong response
  RECONNECT_BASE_DELAY: 1000,      // ms - Base delay for exponential backoff
  RECONNECT_MAX_DELAY: 30000,      // ms - Max reconnect delay
  RECONNECT_MAX_ATTEMPTS: 10,      // Max reconnection attempts
  HEARTBEAT_INTERVAL: 5000,        // ms - Firmware heartbeat interval
  
  // USB enumeration
  USB_ENUM_WAIT: 2000,             // ms - Wait time for USB enumeration
  PORT_OPEN_RETRY_BACKOFF: 200,    // ms - Base backoff for port open retries
  PORT_OPEN_MAX_ATTEMPTS: 5        // Max attempts to open serial port
};

// ============================================================================
// SIZE LIMITS
// ============================================================================

export const LIMITS = {
  // HID report limits
  HID_MOUSE_MOVE_MAX: 127,         // Max movement per HID report (signed byte)
  HID_MOUSE_MOVE_MIN: -127,        // Min movement per HID report
  HID_SCROLL_MAX: 127,             // Max scroll per HID report
  HID_SCROLL_MIN: -127,            // Min scroll per HID report
  
  // Command limits
  TEXT_MAX_LENGTH: 1000,           // Max characters in type_text command
  LINE_MAX_LENGTH: 1024,           // Max length of JSON command line
  
  // Movement parameters
  SMOOTH_MOVE_MIN_DISTANCE: 10,    // Pixels - Below this, don't smooth
  SMOOTH_MOVE_MIN_STEPS: 5,        // Minimum interpolation steps
  SMOOTH_MOVE_MAX_STEPS: 30,       // Maximum interpolation steps
  SMOOTH_MOVE_STEP_PIXELS: 20,     // Pixels per step for step calculation
  
  // Timing limits
  SMOOTH_MOVE_MIN_DURATION: 100,   // ms - Minimum movement duration
  SMOOTH_MOVE_MAX_DURATION: 2000,  // ms - Maximum movement duration
  DRAG_DEFAULT_DURATION: 300,      // ms - Default drag duration
  DRAG_MAX_DURATION: 10000         // ms - Maximum drag duration
};

// ============================================================================
// SPEED CONSTANTS
// ============================================================================

export const SPEED = {
  // Human-like movement speeds (pixels per millisecond)
  MIN_PIXEL_PER_MS: 1.0,
  MAX_PIXEL_PER_MS: 1.5,
  
  // Random delay ranges for human-like behavior
  ACTION_DELAY_MIN: 50,            // ms
  ACTION_DELAY_MAX: 200            // ms
};

// ============================================================================
// USB DEVICE IDENTIFICATION
// ============================================================================

export const USB_DEVICE = {
  VENDOR_ID: '303a',               // Espressif
  PRODUCT_ID: '1001',              // ESP32-S3
  BAUD_RATE: 115200
};

// ============================================================================
// ERROR MESSAGES
// ============================================================================

export const ERROR_MESSAGES = {
  DEVICE_NOT_READY: 'Device not ready. Call connect() first.',
  DEVICE_NOT_AVAILABLE: 'Device not available',
  DEVICE_OFFLINE: 'Device offline',
  NO_SERIAL_PORTS: 'No serial ports available to connect. Check USB connection.',
  HELLO_TIMEOUT: 'Device did not send hello message within timeout',
  PONG_TIMEOUT: 'Device did not respond to ping',
  COMMAND_TIMEOUT: 'Command timeout',
  CONNECTION_FAILED: 'Failed to connect to device',
  PORT_OPEN_FAILED: 'Failed to open serial port',
  SEND_FAILED: 'Failed to send command',
  PARSE_FAILED: 'Failed to parse response',
  VALIDATION_FAILED: 'Validation failed',
  EXECUTION_FAILED: 'Execution failed'
};

// ============================================================================
// FILE PATHS
// ============================================================================

export const PATHS = {
  LAST_PORT_FILE: '.last_port'    // Relative to device-shadow root
};

// ============================================================================
// LOGGING
// ============================================================================

export const LOG_PREFIX = {
  SERIAL_HID: '[SerialHID]',
  DEVICE_SHADOW: '[DeviceShadow]',
  VALIDATOR: '[Validator]',
  SANITIZER: '[Sanitizer]',
  NORMALIZER: '[Normalizer]',
  MOUSE_ENGINE: '[MouseEngine]',
  QUEUE: '[CommandQueue]',
  STATE: '[ShadowState]',
  API: '[API]'
};
