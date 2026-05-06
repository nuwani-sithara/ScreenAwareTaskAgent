/**
 * Device Shadow - Main Entry Point
 * 
 * Orchestrates the complete HID control flow:
 * 1. Connect to ESP32-S3 device
 * 2. Validate and sanitize commands
 * 3. Normalize into HID primitives
 * 4. Queue and execute commands
 * 5. Track state and provide feedback
 * 
 * This is the primary interface for external agents.
 */

import { HIDActuator } from './actuation/hidActuator';
import { LocalActuator } from './actuation/localActuator';
import { Validator } from './transport/validator';
import { Sanitizer } from './transport/sanitizer';
import { Normalizer } from './transport/normalizer';
import { MouseEngine } from './motion/mouseEngine';
import { CommandQueue } from './queue/commandQueue';
import { ShadowState } from './state/shadowState';

export class DeviceShadow {
  private hidActuator: HIDActuator;
  private localActuator: LocalActuator;
  private queue: CommandQueue;
  private state: ShadowState;
  private autoReconnect: boolean = true;
  
  constructor() {
    this.state = new ShadowState();
    this.hidActuator = new HIDActuator(undefined, () => this.state.updateHeartbeat());
    this.localActuator = new LocalActuator();
    this.queue = new CommandQueue();
  }
  
  /**
   * Initialize and connect to device
   */
  async connect(): Promise<void> {
    console.log('[DeviceShadow] Connecting to HID device...');
    
    try {
      await this.hidActuator.connect();
      const firmwareVersion = this.hidActuator.getFirmwareVersion();
      const portPath = this.hidActuator.getPortPath();
      this.state.setConnected(true, portPath || undefined, firmwareVersion || undefined);
      console.log('[DeviceShadow] Connected successfully');
      console.log('[DeviceShadow] HID ready for work');
    } catch (error: any) {
      console.error('[DeviceShadow] Connection failed:', error.message);
      throw error;
    }
  }
  
  /**
   * Execute a high-level command
   * This is the main entry point for agents
   */
  async executeCommand(command: any): Promise<void> {
    // Process the given command through the full pipeline (validate -> sanitize -> normalize -> smoothing -> enqueue -> execute)
    const processOneCommand = async (cmd: any) => {
      // Step 1: Validate
      const validation = Validator.validate(cmd);
      if (!validation.valid) {
        throw new Error(`Validation failed: ${validation.error}`);
      }

      // Step 2: Sanitize
      const sanitized = Sanitizer.sanitize(cmd);

      // Step 3: Normalize into primitives
      const primitives = Normalizer.normalize(sanitized);

      // Step 4: Handle special cases (motion smoothing)
      let executionSteps: any[] = [];

      // Use MouseEngine for smooth mouse_move with smooth flag
      if (cmd.cmd === 'mouse_move' && cmd.smooth) {
        const steps = MouseEngine.generateSmoothMovement(
          cmd.dx,
          cmd.dy,
          cmd.duration
        );

        executionSteps = steps.map((step: any) => ({
          cmd: 'mouse_move',
          dx: step.dx,
          dy: step.dy,
          _delay: step.delay
        }));
      }
      // Use MouseEngine for mouse_drag to generate smooth drag path
      else if (cmd.cmd === 'mouse_drag') {
        const dragSteps = MouseEngine.generateDragSequence(
          cmd.dx,
          cmd.dy,
          cmd.button || 'left',
          cmd.duration
        );
        executionSteps = dragSteps;
      }
      else {
        executionSteps = primitives;
      }

      // Step 5: Enqueue commands with fallback mapping
      const actuationSteps = this.buildActuationSteps(cmd, executionSteps);
      for (const step of actuationSteps) {
        this.queue.enqueue(step);
      }

      // Step 6: Process queue (await completion of these enqueued steps)
      await this.queue.process(async (c) => {
        await this.executePrimitive(c);
      });
    };

    // Execute the original command without implicit cursor anchoring.
    // Absolute-position orchestration (if needed) must be handled by caller.
    await processOneCommand(command);
  }
  
  /**
   * Execute a single primitive command
   */
  private async executePrimitive(command: any): Promise<void> {
    const primaryCommand = command.primary || command;
    const fallbackCommand = command.fallback || command;

    // Handle delay if specified
    const delayMs = primaryCommand._delay ?? fallbackCommand._delay;
    if (delayMs) {
      await this.delay(delayMs);
    }

    // Debug log for scroll commands
    if (primaryCommand.cmd === 'mouse_scroll') {
      console.log(`[DeviceShadow] Executing scroll command:`, JSON.stringify(primaryCommand));
    }

    const executeHid = async (): Promise<void> => {
      if (primaryCommand._anchorBefore) {
        const anchorSteps = Normalizer.normalize(this.getAnchorCommand());
        for (const anchorStep of anchorSteps) {
          await this.hidActuator.execute(anchorStep);
        }
      }
      await this.hidActuator.execute(this.stripInternalFields(primaryCommand));
    };

    let hidError: Error | null = null;
    const hidAvailable = this.hidActuator.isAvailable();

    if (hidAvailable) {
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          await executeHid();
          this.state.recordHidAttempt('ok');
          this.state.recordExecution(primaryCommand, 'ok');
          return;
        } catch (error: any) {
          hidError = error;
          this.state.recordHidAttempt('error');
          if (attempt === 0) {
            console.warn('[DeviceShadow] HID execution failed, retrying once:', error.message);
          }
        }
      }
    } else {
      hidError = new Error('HID unavailable');
      this.state.recordHidAttempt('error');
    }

    // Attempt reconnection if connection lost
    if (!this.hidActuator.isAvailable() && this.autoReconnect) {
      try {
        await this.reconnect();
      } catch (error: any) {
        console.warn('[DeviceShadow] Reconnect attempt failed, continuing with fallback');
      }
    }

    try {
      if (hidError) {
        console.warn('[DeviceShadow] HID unavailable or failed, engaging fallback actuator');
      }
      await this.localActuator.execute(this.stripInternalFields(fallbackCommand));
      this.state.recordFallbackAttempt('ok');
      this.state.recordExecution(fallbackCommand, 'ok');
      if (hidError) {
        console.warn('[DeviceShadow] Fallback executed successfully after HID failure');
      }
    } catch (error: any) {
      this.state.recordFallbackAttempt('error');
      this.state.recordExecution(fallbackCommand, 'error', error.message);
      throw error;
    }
  }
  
  /**
   * Reconnect to device
   */
  private async reconnect(): Promise<void> {
    console.log('[DeviceShadow] Connection lost, attempting reconnection...');
    this.state.setConnected(false);
    this.state.incrementReconnectAttempts();
    
    try {
      await this.hidActuator.reconnect();
      const firmwareVersion = this.hidActuator.getFirmwareVersion();
      const portPath = this.hidActuator.getPortPath();
      this.state.setConnected(true, portPath || undefined, firmwareVersion || undefined);
      console.log('[DeviceShadow] Reconnected successfully');
      console.log('[DeviceShadow] HID ready for work');
    } catch (error: any) {
      console.error('[DeviceShadow] Reconnection failed:', error.message);
    }
  }
  
  /**
   * Get current device state
   */
  getState(): any {
    return this.state.getState();
  }
  
  /**
   * Get execution statistics
   */
  getStats(): any {
    return this.state.getStats();
  }
  
  /**
   * Check if device is connected
   */
  isConnected(): boolean {
    return this.state.isConnected() && this.hidActuator.isAvailable();
  }
  
  /**
   * Disconnect from device
   */
  async disconnect(): Promise<void> {
    console.log('[DeviceShadow] Disconnecting...');
    this.queue.clear();
    await this.hidActuator.disconnect();
    this.state.setConnected(false);
  }
  
  /**
   * Utility: Delay
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private buildActuationSteps(command: any, executionSteps: any[]): any[] {
    const steps: any[] = [];

    if (command.cmd === 'mouse_move') {
      let cursorX = 0;
      let cursorY = 0;

      executionSteps.forEach((step, index) => {
        const primaryStep = { ...step };
        if (index === 0) {
          primaryStep._anchorBefore = true;
        }

        if (step.cmd === 'mouse_move') {
          cursorX += step.dx;
          cursorY += step.dy;
          steps.push({
            primary: primaryStep,
            fallback: { ...step, dx: cursorX, dy: cursorY }
          });
        } else {
          steps.push({ primary: primaryStep, fallback: { ...step } });
        }
      });

      return steps;
    }

    for (const step of executionSteps) {
      steps.push({ primary: { ...step }, fallback: { ...step } });
    }

    return steps;
  }

  private getAnchorCommand(): any {
    return {
      cmd: 'mouse_move',
      dx: -32767,
      dy: -32767
    };
  }

  private stripInternalFields(command: any): any {
    const cleaned = { ...command };
    delete cleaned._delay;
    delete cleaned._anchorBefore;
    return cleaned;
  }
}

// ============================================================================
// EXAMPLE USAGE
// ============================================================================

async function example() {
  const shadow = new DeviceShadow();
  
  try {
    // Connect to device
    await shadow.connect();
    
    // Move mouse smoothly
    await shadow.executeCommand({
      cmd: 'mouse_move',
      dx: 200,
      dy: 100,
      smooth: true,
      duration: 500
    });
    
    // Click
    await shadow.executeCommand({
      cmd: 'mouse_click',
      button: 'left'
    });
    
    // Type text
    await shadow.executeCommand({
      cmd: 'type_text',
      text: 'Hello from Device Shadow!'
    });
    
    // Get stats
    console.log('Stats:', shadow.getStats());
    
    // Disconnect
    await shadow.disconnect();
    
  } catch (error) {
    console.error('Error:', error);
  }
}

// Export main class
export default DeviceShadow;
