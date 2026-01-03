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
      
      // Add small random jitter for naturalness (±1 pixel)
      const jitterX = Math.random() > 0.5 ? (Math.random() > 0.7 ? 1 : 0) : (Math.random() > 0.7 ? -1 : 0);
      const jitterY = Math.random() > 0.5 ? (Math.random() > 0.7 ? 1 : 0) : (Math.random() > 0.7 ? -1 : 0);
      
      steps.push({
        dx: dx + jitterX,
        dy: dy + jitterY,
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
}
