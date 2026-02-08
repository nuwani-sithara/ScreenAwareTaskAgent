/**
 * Command Queue
 * 
 * Manages execution queue for HID commands:
 * - Sequential execution with timing
 * - Prevents command overlap
 * - Handles errors gracefully
 * - Provides execution feedback
 */

export interface QueuedCommand {
  id: string;
  command: any;
  timestamp: number;
  status: 'pending' | 'executing' | 'completed' | 'failed';
  error?: string;
}

export class CommandQueue {
  private queue: QueuedCommand[] = [];
  private isProcessing: boolean = false;
  private commandIdCounter: number = 0;
  
  /**
   * Add command to queue
   * Returns command ID for tracking
   */
  enqueue(command: any): string {
    const id = `cmd_${++this.commandIdCounter}_${Date.now()}`;
    
    const queuedCommand: QueuedCommand = {
      id,
      command,
      timestamp: Date.now(),
      status: 'pending'
    };
    
    this.queue.push(queuedCommand);
    
    return id;
  }
  
  /**
   * Process queue (call this after adding commands)
   * @param executor - Function that executes a single command
   */
  async process(executor: (cmd: any) => Promise<void>): Promise<void> {
    if (this.isProcessing) {
      return; // Already processing
    }
    
    this.isProcessing = true;
    
    while (this.queue.length > 0) {
      const queuedCmd = this.queue[0];
      queuedCmd.status = 'executing';
      
      try {
        await executor(queuedCmd.command);
        queuedCmd.status = 'completed';
      } catch (error: any) {
        queuedCmd.status = 'failed';
        queuedCmd.error = error.message;
        console.error(`[CommandQueue] Command ${queuedCmd.id} failed:`, error.message);
      }
      
      // Remove from queue
      this.queue.shift();
    }
    
    this.isProcessing = false;
  }
  
  /**
   * Get current queue status
   */
  getStatus(): {
    queueLength: number;
    isProcessing: boolean;
    pending: number;
    executing: number;
  } {
    return {
      queueLength: this.queue.length,
      isProcessing: this.isProcessing,
      pending: this.queue.filter(c => c.status === 'pending').length,
      executing: this.queue.filter(c => c.status === 'executing').length
    };
  }
  
  /**
   * Get command by ID
   */
  getCommand(id: string): QueuedCommand | undefined {
    return this.queue.find(c => c.id === id);
  }
  
  /**
   * Clear queue (emergency stop)
   */
  clear(): void {
    this.queue = [];
    this.isProcessing = false;
  }
  
  /**
   * Check if queue is empty
   */
  isEmpty(): boolean {
    return this.queue.length === 0;
  }
}
