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

import { SerialHID } from './hid/serialHID';
import { Validator } from './transport/validator';
import { Sanitizer } from './transport/sanitizer';
import { Normalizer } from './transport/normalizer';
import { MouseEngine } from './motion/mouseEngine';
import { CommandQueue } from './queue/commandQueue';
import { ShadowState } from './state/shadowState';

export class DeviceShadow {
  private hid: SerialHID;
  private queue: CommandQueue;
  private state: ShadowState;
  private autoReconnect: boolean = true;
  
  constructor() {
    this.hid = new SerialHID();
    this.queue = new CommandQueue();
    this.state = new ShadowState();
  }
  
  /**
   * Initialize and connect to device
   */
  async connect(): Promise<void> {
    console.log('[DeviceShadow] Connecting to HID device...');
    
    try {
      await this.hid.connect();
      this.state.setConnected(true);
      console.log('[DeviceShadow] Connected successfully');
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
      } else {
        executionSteps = primitives;
      }

      // Step 5: Enqueue commands
      for (const step of executionSteps) {
        this.queue.enqueue(step);
      }

      // Step 6: Process queue (await completion of these enqueued steps)
      await this.queue.process(async (c) => {
        await this.executePrimitive(c);
      });
    };

    // If this is a mouse_move, first execute a deterministic anchor move to top-left
    if (command.cmd === 'mouse_move') {
      const anchor = {
        cmd: 'mouse_move',
        dx: -1000,
        dy: -1000,
        smooth: true,
        duration: 300
      };

      // Execute anchor first (will go through full normalization/smoothing pipeline)
      await processOneCommand(anchor);
    }

    // Finally execute the original command
    await processOneCommand(command);
  }
  
  /**
   * Execute a single primitive command
   */
  private async executePrimitive(command: any): Promise<void> {
    // Handle delay if specified
    if (command._delay) {
      await this.delay(command._delay);
      delete command._delay;
    }
    
    try {
      const response = await this.hid.sendCommand(command);
      
      if (response.status === 'ok') {
        this.state.recordExecution(command, 'ok');
      } else {
        this.state.recordExecution(command, 'error', response.msg);
        throw new Error(`Device returned error: ${response.error} - ${response.msg}`);
      }
    } catch (error: any) {
      this.state.recordExecution(command, 'error', error.message);
      
      // Attempt reconnection if connection lost
      if (!this.hid.isConnected() && this.autoReconnect) {
        await this.reconnect();
      }
      
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
      await this.hid.reconnect();
      this.state.setConnected(true);
      console.log('[DeviceShadow] Reconnected successfully');
    } catch (error: any) {
      console.error('[DeviceShadow] Reconnection failed:', error.message);
      throw error;
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
    return this.state.isConnected() && this.hid.isConnected();
  }
  
  /**
   * Disconnect from device
   */
  async disconnect(): Promise<void> {
    console.log('[DeviceShadow] Disconnecting...');
    this.queue.clear();
    await this.hid.disconnect();
    this.state.setConnected(false);
  }
  
  /**
   * Utility: Delay
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
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
