/**
 * Command Sanitizer
 * 
 * Sanitizes validated commands to ensure safety:
 * - Clamps values to safe ranges
 * - Removes potentially harmful data
 * - Ensures HID protocol compliance
 */

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
   */
  private static sanitizeMouseScroll(cmd: any): any {
    // Clamp scroll to reasonable range
    cmd.scroll = Math.round(this.clamp(cmd.scroll, -10, 10));
    
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
   * Utility: Clamp value between min and max
   */
  private static clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, value));
  }
}
