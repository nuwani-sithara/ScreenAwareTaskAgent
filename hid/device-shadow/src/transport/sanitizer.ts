/**
 * Command Sanitizer
 * 
 * Sanitizes validated commands to ensure safety:
 * - Clamps values to safe ranges
 * - Removes potentially harmful data
 * - Ensures HID protocol compliance
 * - Converts string key names to numeric keycodes
 */

import { keyToKeycode, isValidKey } from './keycodes';

export class Sanitizer {
  
  /**
   * Sanitize any command
   */
  static sanitize(command: any): any {
    const sanitized = { ...command };
    
    switch (command.cmd) {
      case 'mouse_move':
        return this.sanitizeMouseMove(sanitized);
      case 'mouse_scroll':
        return this.sanitizeMouseScroll(sanitized);
      case 'mouse_drag':
        return this.sanitizeMouseDrag(sanitized);
      case 'key_press':
        return this.sanitizeKeyPress(sanitized);
      case 'key_release':
        return this.sanitizeKeyRelease(sanitized);
      case 'type_text':
        return this.sanitizeTypeText(sanitized);
      default:
        // Other commands don't need sanitization
        return sanitized;
    }
  }
  
  /**
   * Sanitize mouse_move command
   * Clamps movement to HID-safe range (-127 to 127 per report)
   */
  private static sanitizeMouseMove(cmd: any): any {
    // Clamp to safe range for single HID report
    // Note: Large movements will be split by normalizer
    cmd.dx = Math.round(this.clamp(cmd.dx, -127, 127));
    cmd.dy = Math.round(this.clamp(cmd.dy, -127, 127));
    
    return cmd;
  }
  
  /**
   * Sanitize mouse_scroll command
   * Clamps scroll amount to reasonable range
   * Supports both legacy 'scroll' field and new 'deltaX'/'deltaY' fields
   */
  private static sanitizeMouseScroll(cmd: any): any {
    // Handle legacy scroll field
    if (cmd.scroll !== undefined) {
      cmd.scroll = Math.round(this.clamp(cmd.scroll, -10, 10));
    }
    
    // Handle deltaY (vertical scroll)
    if (cmd.deltaY !== undefined) {
      cmd.deltaY = Math.round(this.clamp(cmd.deltaY, -10, 10));
    }
    
    // Handle deltaX (horizontal scroll)
    if (cmd.deltaX !== undefined) {
      cmd.deltaX = Math.round(this.clamp(cmd.deltaX, -10, 10));
    }
    
    return cmd;
  }

  /**
   * Sanitize mouse_drag command
   */
  private static sanitizeMouseDrag(cmd: any): any {
    // Clamp each axis per single report expectation
    cmd.dx = Math.round(this.clamp(cmd.dx, -2000, 2000));
    cmd.dy = Math.round(this.clamp(cmd.dy, -2000, 2000));

    // Clamp duration to reasonable bounds
    if (cmd.duration === undefined || typeof cmd.duration !== 'number') cmd.duration = 300;
    cmd.duration = Math.round(this.clamp(cmd.duration, 0, 10000));

    return cmd;
  }
  
  /**
   * Sanitize type_text command
   * Removes non-printable characters and limits length
   */
  private static sanitizeTypeText(cmd: any): any {
    let text = cmd.text;
    
    // Remove control characters except tab, newline
    text = text.replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]/g, '');
    
    // Limit length
    if (text.length > 1000) {
      text = text.substring(0, 1000);
    }
    
    cmd.text = text;
    return cmd;
  }
  
  /**
   * Sanitize key_press command
   * Converts string key names to numeric HID keycodes
   */
  private static sanitizeKeyPress(cmd: any): any {
    // If key is a string, convert to keycode
    if (typeof cmd.key === 'string') {
      if (isValidKey(cmd.key)) {
        cmd.key = keyToKeycode(cmd.key);
      } else {
        throw new Error(`Unknown key name: ${cmd.key}`);
      }
    }
    
    // Ensure key is an integer in valid range
    cmd.key = Math.round(this.clamp(cmd.key, 0, 255));
    
    return cmd;
  }
  
  /**
   * Sanitize key_release command
   * Converts string key names to numeric HID keycodes
   */
  private static sanitizeKeyRelease(cmd: any): any {
    // If key is provided and is a string, convert to keycode
    if (cmd.key !== undefined && typeof cmd.key === 'string') {
      if (isValidKey(cmd.key)) {
        cmd.key = keyToKeycode(cmd.key);
      } else {
        throw new Error(`Unknown key name: ${cmd.key}`);
      }
    }
    
    // Ensure key is an integer in valid range (if provided)
    if (cmd.key !== undefined) {
      cmd.key = Math.round(this.clamp(cmd.key, 0, 255));
    }
    
    return cmd;
  }
  
  /**
   * Utility: Clamp value between min and max
   */
  private static clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, value));
  }
}
