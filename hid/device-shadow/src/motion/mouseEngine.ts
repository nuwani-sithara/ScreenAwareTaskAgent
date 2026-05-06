/**
 * Mouse Motion Engine
 * 
 * Generates human-like mouse movements:
 * - Smooth interpolation between points
 * - Realistic acceleration/deceleration
 * - Natural timing
 * - Prevents robotic patterns
 */

export interface Point {
  x: number;
  y: number;
}

export interface MovementStep {
  dx: number;
  dy: number;
  delay: number; // milliseconds to wait after this step
}

export class MouseEngine {
  
  /**
   * Generate smooth movement from current position to target
   * Returns array of movement steps with timing
   * 
   * @param targetDx - Total X movement required
   * @param targetDy - Total Y movement required
   * @param duration - Total movement duration in milliseconds (default: auto)
   */
  static generateSmoothMovement(
    targetDx: number,
    targetDy: number,
    duration?: number
  ): MovementStep[] {
    const distance = Math.sqrt(targetDx * targetDx + targetDy * targetDy);
    
    // For very small movements, just do it directly
    if (distance < 10) {
      return [{
        dx: Math.round(targetDx),
        dy: Math.round(targetDy),
        delay: 10
      }];
    }
    
    // Auto-calculate duration based on distance if not provided
    if (!duration) {
      // Human-like speed: roughly 500-2000 pixels per second
      const pixelsPerMs = 1.0 + Math.random() * 0.5; // 1000-1500 px/s
      duration = Math.max(100, Math.min(2000, distance / pixelsPerMs));
    }
    
    // Number of steps (higher for smoother movement)
    const numSteps = Math.max(5, Math.min(30, Math.ceil(distance / 20)));
    const stepDelay = duration / numSteps;
    
    const steps: MovementStep[] = [];
    let remainingX = targetDx;
    let remainingY = targetDy;
    
    for (let i = 0; i < numSteps; i++) {
      // Ease-in-out interpolation factor
      const t = (i + 1) / numSteps;
      const eased = this.easeInOutCubic(t);
      
      // Calculate target position for this step
      const targetX = targetDx * eased;
      const targetY = targetDy * eased;
      
      // Calculate delta from last position
      const currentX = targetDx - remainingX;
      const currentY = targetDy - remainingY;
      
      const dx = Math.round(targetX - currentX);
      const dy = Math.round(targetY - currentY);
      
      steps.push({
        dx: dx,
        dy: dy,
        delay: Math.round(stepDelay)
      });
      
      remainingX -= dx;
      remainingY -= dy;
    }
    
    // Ensure we reach exact target (compensate for rounding)
    if (remainingX !== 0 || remainingY !== 0) {
      const lastStep = steps[steps.length - 1];
      lastStep.dx += remainingX;
      lastStep.dy += remainingY;
    }
    
    return steps;
  }
  
  /**
   * Ease-in-out cubic interpolation
   * Provides smooth acceleration and deceleration
   */
  private static easeInOutCubic(t: number): number {
    return t < 0.5
      ? 4 * t * t * t
      : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }
  
  /**
   * Generate random human-like delay between actions
   * Returns delay in milliseconds
   */
  static randomDelay(min: number = 50, max: number = 200): number {
    return Math.round(min + Math.random() * (max - min));
  }
  
  /**
   * Generate drag operation command sequence
   * Returns array of commands: button down -> smooth movement -> button up
   * 
   * @param dx - Total X movement
   * @param dy - Total Y movement
   * @param button - Mouse button to use ('left', 'right', 'middle')
   * @param duration - Total drag duration in milliseconds (default: auto)
   */
  static generateDragSequence(
    dx: number,
    dy: number,
    button: 'left' | 'right' | 'middle' = 'left',
    duration?: number
  ): any[] {
    const sequence: any[] = [];
    
    // 1. Press button
    sequence.push({
      cmd: 'mouse_down',
      button: button,
      _delay: 10
    });
    
    // 2. Generate smooth movement path
    const moveSteps = this.generateSmoothMovement(dx, dy, duration);
    for (const step of moveSteps) {
      sequence.push({
        cmd: 'mouse_move',
        dx: step.dx,
        dy: step.dy,
        _delay: step.delay
      });
    }
    
    // 3. Release button (with small delay before release for realism)
    sequence.push({
      cmd: 'mouse_up',
      button: button,
      _delay: 20
    });
    
    return sequence;
  }
}
