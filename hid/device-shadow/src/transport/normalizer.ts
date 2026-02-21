/**
 * Command Normalizer
 * 
 * Normalizes commands into HID-executable primitives:
 * - Splits large movements into multiple reports
 * - Converts high-level actions into HID actions
 * - Ensures timing constraints
 */

import { modifierNameToKeycode, keyToKeycode } from './keycodes';

export interface NormalizedCommand {
  cmd: string;
  [key: string]: any;
}

export class Normalizer {
  
  /**
   * Normalize any command into executable primitives
   * Returns array of commands to execute sequentially
   */
  static normalize(command: any): NormalizedCommand[] {
    switch (command.cmd) {
      case 'mouse_move':
        return this.normalizeMouseMove(command);
      case 'mouse_scroll':
        return this.normalizeMouseScroll(command);
      case 'mouse_drag':
        return this.normalizeMouseDrag(command);
      case 'key_combo':
        return this.normalizeKeyCombo(command);
      default:
        // Most commands don't need normalization
        return [command];
    }
  }
  
  /**
   * Normalize large mouse movements into multiple small movements
   * 
   * HID mouse reports are limited to -127 to +127 per axis per report.
   * Large movements must be split into multiple reports with timing.
   */
  private static normalizeMouseMove(cmd: any): NormalizedCommand[] {
    const { dx, dy } = cmd;
    
    // If movement is small enough for single report
    if (Math.abs(dx) <= 127 && Math.abs(dy) <= 127) {
      return [cmd];
    }
    
    // Split into multiple movements
    const commands: NormalizedCommand[] = [];
    let remainingX = dx;
    let remainingY = dy;
    
    while (remainingX !== 0 || remainingY !== 0) {
      const stepX = this.clamp(remainingX, -127, 127);
      const stepY = this.clamp(remainingY, -127, 127);
      
      commands.push({
        cmd: 'mouse_move',
        dx: stepX,
        dy: stepY
      });
      
      remainingX -= stepX;
      remainingY -= stepY;
    }
    
    return commands;
  }

  /**
   * Normalize mouse_scroll into one or more wheel reports
   * Supports both legacy 'scroll' field and new 'deltaX'/'deltaY' fields
   */
  private static normalizeMouseScroll(cmd: any): NormalizedCommand[] {
    // Handle deltaY (vertical scroll - preferred)
    if (cmd.deltaY !== undefined && cmd.deltaY !== null && !isNaN(cmd.deltaY)) {
      const deltaY = cmd.deltaY;
      if (Math.abs(deltaY) <= 127) return [cmd];
      
      const commands: NormalizedCommand[] = [];
      let remaining = deltaY;
      
      while (remaining !== 0) {
        const step = this.clamp(remaining, -127, 127);
        commands.push({ cmd: 'mouse_scroll', deltaY: step, deltaX: cmd.deltaX || 0 });
        remaining -= step;
      }
      
      return commands;
    }
    
    // Handle deltaX (horizontal scroll alone)
    if (cmd.deltaX !== undefined && cmd.deltaX !== null && !isNaN(cmd.deltaX)) {
      const deltaX = cmd.deltaX;
      if (Math.abs(deltaX) <= 127) return [cmd];
      
      const commands: NormalizedCommand[] = [];
      let remaining = deltaX;
      
      while (remaining !== 0) {
        const step = this.clamp(remaining, -127, 127);
        commands.push({ cmd: 'mouse_scroll', deltaX: step, deltaY: 0 });
        remaining -= step;
      }
      
      return commands;
    }
    
    // Handle legacy scroll field (fallback)
    if (cmd.scroll !== undefined && cmd.scroll !== null && !isNaN(cmd.scroll)) {
      const scroll = cmd.scroll;
      if (Math.abs(scroll) <= 127) return [cmd];
      
      const commands: NormalizedCommand[] = [];
      let remaining = scroll;
      
      while (remaining !== 0) {
        const step = this.clamp(remaining, -127, 127);
        commands.push({ cmd: 'mouse_scroll', scroll: step });
        remaining -= step;
      }
      
      return commands;
    }
    
    // No valid scroll field - return command as-is (will fail validation later)
    return [cmd];
  }

  /**
   * Normalize a drag into press + multiple move steps + release
   */
  private static normalizeMouseDrag(cmd: any): NormalizedCommand[] {
    const { dx, dy, duration } = cmd;

    // First, split movement into per-report steps using mouse_move normalizer
    const moveParts = this.normalizeMouseMove({ cmd: 'mouse_move', dx, dy });

    const totalSteps = moveParts.length;
    const commands: NormalizedCommand[] = [];

    // Start with mouse_down (default left button unless specified)
    const button = cmd.button || 'left';
    commands.push({ cmd: 'mouse_down', button });

    // Distribute duration across steps (simple even spacing)
    const perStepDelay = totalSteps > 0 ? Math.max(0, Math.round((duration || 300) / totalSteps)) : 0;

    for (const part of moveParts) {
      const stepCmd: any = { ...part };
      if (perStepDelay > 0) stepCmd._delay = perStepDelay;
      commands.push(stepCmd);
    }

    // End with mouse_up
    commands.push({ cmd: 'mouse_up', button });

    return commands;
  }
  
  /**
   * Normalize key_combo into press sequence with proper timing
   * 
   * Sequence:
   * 1. Press all modifiers (with 5ms delay between each)
   * 2. Press main key (with 5ms delay)
   * 3. Release main key (with 5ms delay)
   * 4. Release all modifiers (with 5ms delay between each)
   */
  private static normalizeKeyCombo(cmd: any): NormalizedCommand[] {
    const modifiers = cmd.modifiers || [];
    const key = cmd.key;
    const commands: NormalizedCommand[] = [];
    
    // Convert modifier names to keycodes
    const modifierKeycodes = modifiers.map((mod: string) => modifierNameToKeycode(mod));
    
    // Convert main key name to keycode
    const keyKeycode = keyToKeycode(key);
    
    // 1. Press all modifiers
    for (const modKeycode of modifierKeycodes) {
      commands.push({
        cmd: 'key_press',
        key: modKeycode,
        _delay: 5
      });
    }
    
    // 2. Press main key
    commands.push({
      cmd: 'key_press',
      key: keyKeycode,
      _delay: 10  // Slightly longer delay for main key
    });
    
    // 3. Release main key
    commands.push({
      cmd: 'key_release',
      key: keyKeycode,
      _delay: 5
    });
    
    // 4. Release all modifiers (in reverse order)
    for (let i = modifierKeycodes.length - 1; i >= 0; i--) {
      commands.push({
        cmd: 'key_release',
        key: modifierKeycodes[i],
        _delay: 5
      });
    }
    
    return commands;
  }
  
  /**
   * 
  /**
   * Utility: Clamp value between min and max
   */
  private static clamp(value: number, min: number, max: number): number {
    if (value < min) return min;
    if (value > max) return max;
    return Math.round(value);
  }
}
