/**
 * Command Normalizer
 * 
 * Normalizes commands into HID-executable primitives:
 * - Splits large movements into multiple reports
 * - Converts high-level actions into HID actions
 * - Ensures timing constraints
 */

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
   */
  private static normalizeMouseScroll(cmd: any): NormalizedCommand[] {
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
   * Utility: Clamp value between min and max
   */
  private static clamp(value: number, min: number, max: number): number {
    if (value < min) return min;
    if (value > max) return max;
    return Math.round(value);
  }
}
