/**
 * Command Validator
 * 
 * Validates incoming commands before processing:
 * - Schema validation
 * - Parameter bounds checking
 * - Type verification
 * - Security checks
 */

import { isValidModifier, isValidKey } from './keycodes';

export interface ValidationResult {
  valid: boolean;
  error?: string;
  sanitized?: any;
}

export class Validator {
  
  /**
   * Validate any command
   */
  static validate(command: any): ValidationResult {
    // Check if command is an object
    if (typeof command !== 'object' || command === null) {
      return { valid: false, error: 'Command must be an object' };
    }
    
    // Check for cmd field
    if (!command.cmd || typeof command.cmd !== 'string') {
      return { valid: false, error: 'Missing or invalid "cmd" field' };
    }
    
    // Route to specific validator
    switch (command.cmd) {
      case 'mouse_move':
        return this.validateMouseMove(command);
      case 'mouse_down':
        return this.validateMouseDown(command);
      case 'mouse_up':
        return this.validateMouseUp(command);
      case 'mouse_drag':
        return this.validateMouseDrag(command);
      case 'ack':
        return { valid: true };
      case 'mouse_click':
        return this.validateMouseClick(command);
      case 'mouse_scroll':
        return this.validateMouseScroll(command);
      case 'key_press':
        return this.validateKeyPress(command);
      case 'key_release':
        return this.validateKeyRelease(command);
      case 'key_combo':
        return this.validateKeyCombo(command);
      case 'type_text':
        return this.validateTypeText(command);
      case 'system':
        return this.validateSystem(command);
      default:
        return { valid: false, error: `Unknown command: ${command.cmd}` };
    }
  }

  private static validateMouseDown(cmd: any): ValidationResult {
    const button = cmd.button;
    if (button !== undefined && typeof button !== 'string') {
      return { valid: false, error: 'button must be a string' };
    }
    return { valid: true };
  }

  private static validateMouseUp(cmd: any): ValidationResult {
    const button = cmd.button;
    if (button !== undefined && typeof button !== 'string') {
      return { valid: false, error: 'button must be a string' };
    }
    return { valid: true };
  }
  
  /**
   * Validate mouse_move command
   */
  private static validateMouseMove(cmd: any): ValidationResult {
    const dx = cmd.dx;
    const dy = cmd.dy;
    
    if (typeof dx !== 'number' || typeof dy !== 'number') {
      return { valid: false, error: 'dx and dy must be numbers' };
    }
    
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) {
      return { valid: false, error: 'dx and dy must be finite numbers' };
    }
    
    // Allow movement, will be clamped by sanitizer
    return { valid: true };
  }
  
  /**
   * Validate mouse_click command
   */
  private static validateMouseClick(cmd: any): ValidationResult {
    const button = cmd.button;
    
    if (typeof button !== 'string') {
      return { valid: false, error: 'button must be a string' };
    }
    
    const validButtons = ['left', 'right', 'middle'];
    if (!validButtons.includes(button)) {
      return { valid: false, error: `button must be one of: ${validButtons.join(', ')}` };
    }
    
    return { valid: true };
  }
  
  /**
   * Validate mouse_scroll command
   */
  private static validateMouseScroll(cmd: any): ValidationResult {
    // Support both legacy 'scroll' field and new 'deltaX'/'deltaY' fields
    const scroll = cmd.scroll;
    const deltaX = cmd.deltaX;
    const deltaY = cmd.deltaY;
    
    // At least one field must be present
    if (scroll === undefined && deltaX === undefined && deltaY === undefined) {
      return { valid: false, error: 'Must provide scroll, deltaY, or deltaX' };
    }
    
    // Validate scroll if present (legacy format)
    if (scroll !== undefined) {
      if (typeof scroll !== 'number' || !Number.isFinite(scroll)) {
        return { valid: false, error: 'scroll must be a finite number' };
      }
    }
    
    // Validate deltaX if present
    if (deltaX !== undefined) {
      if (typeof deltaX !== 'number' || !Number.isFinite(deltaX)) {
        return { valid: false, error: 'deltaX must be a finite number' };
      }
    }
    
    // Validate deltaY if present
    if (deltaY !== undefined) {
      if (typeof deltaY !== 'number' || !Number.isFinite(deltaY)) {
        return { valid: false, error: 'deltaY must be a finite number' };
      }
    }
    
    return { valid: true };
  }

  /**
   * Validate mouse_drag command
   * Expected fields: dx, dy, duration (ms, optional)
   */
  private static validateMouseDrag(cmd: any): ValidationResult {
    const dx = cmd.dx;
    const dy = cmd.dy;
    const duration = cmd.duration !== undefined ? cmd.duration : 300;

    if (typeof dx !== 'number' || typeof dy !== 'number') {
      return { valid: false, error: 'dx and dy must be numbers' };
    }

    if (!Number.isFinite(dx) || !Number.isFinite(dy)) {
      return { valid: false, error: 'dx and dy must be finite numbers' };
    }

    if (typeof duration !== 'number' || !Number.isFinite(duration) || duration < 0 || duration > 10000) {
      return { valid: false, error: 'duration must be a finite number between 0 and 10000' };
    }

    return { valid: true };
  }
  
  /**
   * Validate key_press command
   */
  private static validateKeyPress(cmd: any): ValidationResult {
    const key = cmd.key;
    
    // Accept both string key names and numeric keycodes
    if (typeof key === 'string') {
      // String keys will be converted by sanitizer
      if (!key || key.length === 0) {
        return { valid: false, error: 'key string cannot be empty' };
      }
      return { valid: true };
    }
    
    if (typeof key === 'number') {
      if (!Number.isInteger(key) || key < 0 || key > 255) {
        return { valid: false, error: 'key must be an integer between 0 and 255' };
      }
      return { valid: true };
    }
    
    return { valid: false, error: 'key must be a string (key name) or number (HID keycode)' };
  }
  
  /**
   * Validate key_release command
   */
  private static validateKeyRelease(cmd: any): ValidationResult {
    // key is optional (if missing, releases all keys)
    if (cmd.key !== undefined) {
      const key = cmd.key;
      
      // Accept both string key names and numeric keycodes
      if (typeof key === 'string') {
        // String keys will be converted by sanitizer
        if (!key || key.length === 0) {
          return { valid: false, error: 'key string cannot be empty' };
        }
        return { valid: true };
      }
      
      if (typeof key === 'number') {
        if (!Number.isInteger(key) || key < 0 || key > 255) {
          return { valid: false, error: 'key must be an integer between 0 and 255' };
        }
        return { valid: true };
      }
      
      return { valid: false, error: 'key must be a string (key name) or number (HID keycode)' };
    }
    
    return { valid: true };
  }
  
  /**
   * Validate key_combo command
   */
  private static validateKeyCombo(cmd: any): ValidationResult {
    const modifiers = cmd.modifiers;
    const key = cmd.key;
    
    // Modifiers must be an array (can be empty)
    if (!Array.isArray(modifiers)) {
      return { valid: false, error: 'modifiers must be an array' };
    }
    
    // Validate each modifier name
    for (const mod of modifiers) {
      if (typeof mod !== 'string') {
        return { valid: false, error: 'Each modifier must be a string' };
      }
      if (!isValidModifier(mod)) {
        return { valid: false, error: `Invalid modifier: ${mod}` };
      }
    }
    
    // Key must be a string
    if (typeof key !== 'string') {
      return { valid: false, error: 'key must be a string' };
    }
    
    // Validate key name
    if (!isValidKey(key)) {
      return { valid: false, error: `Invalid key: ${key}` };
    }
    
    return { valid: true };
  }
  
  /**
   * Validate type_text command
   */
  private static validateTypeText(cmd: any): ValidationResult {
    const text = cmd.text;
    
    if (typeof text !== 'string') {
      return { valid: false, error: 'text must be a string' };
    }
    
    if (text.length === 0) {
      return { valid: false, error: 'text cannot be empty' };
    }
    
    if (text.length > 1000) {
      return { valid: false, error: 'text too long (max 1000 characters)' };
    }
    
    return { valid: true };
  }
  
  /**
   * Validate system command
   */
  private static validateSystem(cmd: any): ValidationResult {
    const code = cmd.code;
    
    if (typeof code !== 'number') {
      return { valid: false, error: 'code must be a number' };
    }
    
    if (!Number.isInteger(code) || code < 0 || code > 65535) {
      return { valid: false, error: 'code must be an integer between 0 and 65535' };
    }
    
    return { valid: true };
  }
}
