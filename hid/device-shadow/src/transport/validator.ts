/**
 * Command Validator
 * 
 * Validates incoming commands before processing:
 * - Schema validation
 * - Parameter bounds checking
 * - Type verification
 * - Security checks
 */

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
      case 'type_text':
        return this.validateTypeText(command);
      case 'system':
        return this.validateSystem(command);
      default:
        return { valid: false, error: `Unknown command: ${command.cmd}` };
    }
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
    const scroll = cmd.scroll;
    
    if (typeof scroll !== 'number') {
      return { valid: false, error: 'scroll must be a number' };
    }
    
    if (!Number.isFinite(scroll)) {
      return { valid: false, error: 'scroll must be a finite number' };
    }
    
    return { valid: true };
  }
  
  /**
   * Validate key_press command
   */
  private static validateKeyPress(cmd: any): ValidationResult {
    const key = cmd.key;
    
    if (typeof key !== 'number') {
      return { valid: false, error: 'key must be a number (HID keycode)' };
    }
    
    if (!Number.isInteger(key) || key < 0 || key > 255) {
      return { valid: false, error: 'key must be an integer between 0 and 255' };
    }
    
    return { valid: true };
  }
  
  /**
   * Validate key_release command
   */
  private static validateKeyRelease(cmd: any): ValidationResult {
    // key is optional (if missing, releases all keys)
    if (cmd.key !== undefined) {
      const key = cmd.key;
      
      if (typeof key !== 'number') {
        return { valid: false, error: 'key must be a number (HID keycode)' };
      }
      
      if (!Number.isInteger(key) || key < 0 || key > 255) {
        return { valid: false, error: 'key must be an integer between 0 and 255' };
      }
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
