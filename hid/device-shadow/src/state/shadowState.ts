/**
 * Shadow State Manager
 * 
 * Maintains device shadow state:
 * - Current execution state
 * - Last executed command
 * - Device capabilities
 * - Connection status
 * - Error history
 */

export interface DeviceCapabilities {
  mouse: boolean;
  keyboard: boolean;
  consumer: boolean;
}

export interface ExecutionState {
  lastCommand: any | null;
  lastCommandTime: number | null;
  lastCommandStatus: 'ok' | 'error' | null;
  lastError: string | null;
  commandsExecuted: number;
  commandsFailed: number;
}

export interface ConnectionState {
  connected: boolean;
  devicePath: string | null;
  firmwareVersion: string | null;
  connectedSince: number | null;
  lastHeartbeat: number | null;
  reconnectAttempts: number;
}

export class ShadowState {
  private capabilities: DeviceCapabilities = {
    mouse: true,
    keyboard: true,
    consumer: false // Not yet implemented in firmware
  };
  
  private execution: ExecutionState = {
    lastCommand: null,
    lastCommandTime: null,
    lastCommandStatus: null,
    lastError: null,
    commandsExecuted: 0,
    commandsFailed: 0
  };
  
  private connection: ConnectionState = {
    connected: false,
    devicePath: null,
    firmwareVersion: null,
    connectedSince: null,
    lastHeartbeat: null,
    reconnectAttempts: 0
  };
  
  /**
   * Update connection state
   */
  setConnected(connected: boolean, devicePath?: string, firmwareVersion?: string): void {
    this.connection.connected = connected;
    
    if (connected) {
      this.connection.devicePath = devicePath || null;
      this.connection.firmwareVersion = firmwareVersion || null;
      this.connection.connectedSince = Date.now();
      this.connection.lastHeartbeat = Date.now();
      this.connection.reconnectAttempts = 0;
    } else {
      this.connection.connectedSince = null;
      this.connection.lastHeartbeat = null;
    }
  }
  
  /**
   * Update heartbeat timestamp
   */
  updateHeartbeat(): void {
    this.connection.lastHeartbeat = Date.now();
  }
  
  /**
   * Increment reconnect attempts
   */
  incrementReconnectAttempts(): void {
    this.connection.reconnectAttempts++;
  }
  
  /**
   * Update execution state after command
   */
  recordExecution(command: any, status: 'ok' | 'error', error?: string): void {
    this.execution.lastCommand = command;
    this.execution.lastCommandTime = Date.now();
    this.execution.lastCommandStatus = status;
    this.execution.lastError = error || null;
    
    if (status === 'ok') {
      this.execution.commandsExecuted++;
    } else {
      this.execution.commandsFailed++;
    }
  }
  
  /**
   * Get current state snapshot
   */
  getState(): {
    capabilities: DeviceCapabilities;
    execution: ExecutionState;
    connection: ConnectionState;
  } {
    return {
      capabilities: { ...this.capabilities },
      execution: { ...this.execution },
      connection: { ...this.connection }
    };
  }
  
  /**
   * Get capabilities
   */
  getCapabilities(): DeviceCapabilities {
    return { ...this.capabilities };
  }
  
  /**
   * Check if device is connected
   */
  isConnected(): boolean {
    return this.connection.connected;
  }
  
  /**
   * Get connection uptime in milliseconds
   */
  getUptime(): number {
    if (!this.connection.connectedSince) {
      return 0;
    }
    return Date.now() - this.connection.connectedSince;
  }
  
  /**
   * Get execution statistics
   */
  getStats(): {
    totalCommands: number;
    successRate: number;
    uptime: number;
  } {
    const total = this.execution.commandsExecuted + this.execution.commandsFailed;
    const successRate = total > 0 
      ? (this.execution.commandsExecuted / total) * 100 
      : 0;
    
    return {
      totalCommands: total,
      successRate: Math.round(successRate * 100) / 100,
      uptime: this.getUptime()
    };
  }
  
  /**
   * Reset execution statistics
   */
  resetStats(): void {
    this.execution.commandsExecuted = 0;
    this.execution.commandsFailed = 0;
  }
}
