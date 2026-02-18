import { SerialPort } from 'serialport';
import { ReadlineParser } from '@serialport/parser-readline';
import * as fs from 'fs';
import * as path from 'path';
import { randomUUID } from 'crypto';

/**
 * SerialHID - USB CDC Serial interface to ESP32-S3 HID device
 * 
 * Manages:
 * - Device discovery and connection
 * - Command transmission with ACK tracking
 * - Response parsing
 * - Auto-reconnection
 * - Error handling
 */

export interface HIDResponse {
  status: 'ok' | 'error' | 'ready';
  cmd?: string;
  error?: string;
  msg?: string;
  device?: string;
}

export interface HelloMessage {
  type: 'hello';
  status: 'ready';
  firmwareVersion: string;
}

export interface PongMessage {
  type: 'pong';
}

export interface AckMessage {
  type: 'ack';
  commandId: string;
  status: 'ok' | 'error';
  message?: string;
}

export interface ReadyForNextMessage {
  type: 'readyForNext';
}

export type ControlMessage = HelloMessage | PongMessage | AckMessage | ReadyForNextMessage;

export interface HIDCommand {
  cmd: string;
  meta?: {
    commandId?: string;
  };
  [key: string]: any;
}

interface InFlightCommand {
  commandId: string;
  command: HIDCommand;
  resolve: (response: HIDResponse | AckMessage) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
  retries: number;
}

export class SerialHID {
  private port: SerialPort | null = null;
  private parser: ReadlineParser | null = null;
  private portPath: string | null = null;
  private isReady: boolean = false;
  private firmwareVersion: string | null = null;
  private responseCallbacks: Map<string, (response: HIDResponse) => void> = new Map();
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private reconnectBaseDelay: number = 1000; // ms
  private autoReconnectEnabled: boolean = true;
  private reconnectTimer: NodeJS.Timeout | null = null;
  
  // ACK-based command tracking
  private inFlightCommands: Map<string, InFlightCommand> = new Map();
  private commandTimeout: number = 500; // ms
  private maxRetries: number = 1;
  private useAckSystem: boolean = true;
  private deviceReady: boolean = true; // Track if device is ready for next command
  
  // Device identification
  private readonly VENDOR_ID = '303a'; // Espressif
  private readonly PRODUCT_ID = '1001'; // ESP32-S3
  private readonly LAST_PORT_FILE = path.join(__dirname, '..', '..', '.last_port');
  
  constructor() {}
  
  /**
   * Discover and connect to ESP32-S3 HID device
   */
  async connect(): Promise<void> {
    console.log('[SerialHID] Discovering ESP32-S3 device...');
    
    const ports = await SerialPort.list();
    console.log('[SerialHID] Available serial ports:');
    ports.forEach(p => console.log(`  - ${p.path} | vid=${p.vendorId || 'n/a'} pid=${p.productId || 'n/a'} manufacturer=${p.manufacturer || 'n/a'}`));
    // Build prioritized candidate list: saved port -> VID/PID match -> ports with product/manufacturer -> all ports
    const candidates: string[] = [];

    // 1) previously used port (if exists)
    try {
      if (fs.existsSync(this.LAST_PORT_FILE)) {
        const saved = fs.readFileSync(this.LAST_PORT_FILE, 'utf8').trim();
        if (saved) {
          candidates.push(saved);
          console.log('[SerialHID] Found previously used port:', saved);
        }
      }
    } catch (e) {
      // ignore read errors
    }

    // 2) VID/PID exact matches
    for (const p of ports) {
      if (p.vendorId?.toLowerCase() === this.VENDOR_ID && p.productId?.toLowerCase() === this.PRODUCT_ID && p.path) {
        if (!candidates.includes(p.path)) candidates.push(p.path);
      }
    }

    // 3) Prefer ports with manufacturer/product metadata
    for (const p of ports) {
      if ((p.manufacturer || p.productId) && p.path && !candidates.includes(p.path)) {
        candidates.push(p.path);
      }
    }

    // 4) Finally, include any remaining ports
    for (const p of ports) {
      if (p.path && !candidates.includes(p.path)) candidates.push(p.path);
    }

    if (candidates.length === 0) {
      throw new Error('No serial ports available to connect. Check USB connection.');
    }

    // Try candidates in order until one successfully opens and reports ready
    let lastErr: any = null;
    for (const candidate of candidates) {
      this.portPath = candidate;
      console.log(`[SerialHID] Trying port candidate: ${candidate}`);
      try {
        await this.openPort();
        // success — persist chosen port
        try {
          fs.writeFileSync(this.LAST_PORT_FILE, candidate, 'utf8');
        } catch (e) {
          // ignore write errors
        }
        return;
      } catch (err: any) {
        console.warn(`[SerialHID] Failed to open ${candidate}: ${err && err.message ? err.message : err}`);
        lastErr = err;
        // try next candidate
      }
    }

    // If we get here, none of the candidates worked
    throw lastErr || new Error('Failed to open any serial port candidates');
  }

  
  /**
   * Get firmware version (if connected)
   */
  getFirmwareVersion(): string | null {
    return this.firmwareVersion;
  }
  
  /**
   * Enable or disable auto-reconnect
   
  
  /**
   * Enable or disable ACK-based command tracking
   */
  setUseAckSystem(enabled: boolean): void {
    this.useAckSystem = enabled;
  }
  
  /**
   * Set command timeout (milliseconds)
   */
  setCommandTimeout(timeout: number): void {
    this.commandTimeout = timeout;
  }
  
  /**
   * Enable or disable automatic reconnection
   */
  setAutoReconnect(enabled: boolean): void {
    this.autoReconnectEnabled = enabled;
    if (!enabled && this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
  
  /**
   * Get the currently used port path (if connected)
   */
  getPortPath(): string | null {
    return this.portPath;
  }
  
  /**
   * Open serial port and set up communication
   */
  private openPort(): Promise<void> {
    const MAX_OPEN_ATTEMPTS = 5;
    const BASE_BACKOFF_MS = 200;

    return new Promise(async (resolve, reject) => {
      if (!this.portPath) {
        reject(new Error('No port path available'));
        return;
      }

      let lastError: any = null;

      for (let attempt = 1; attempt <= MAX_OPEN_ATTEMPTS; attempt++) {
        // Clean up any previous port instance
        try {
          if (this.parser) {
            this.parser.removeAllListeners();
            this.parser = null;
          }
          if (this.port) {
            this.port.removeAllListeners();
            if (this.port.isOpen) {
              try { this.port.close(() => {}); } catch (e) {}
            }
            this.port = null;
          }
        } catch (e) {}

        // Create port for this attempt
        this.port = new SerialPort({
          path: this.portPath,
          baudRate: 115200,
          autoOpen: false
        });

        // Set up parser and handlers
        try {
          this.parser = this.port.pipe(new ReadlineParser({ delimiter: '\n' }));

          // Remove any existing listeners first (defensive)
          this.parser.removeAllListeners('data');
          this.port.removeAllListeners('error');
          this.port.removeAllListeners('close');

          // Raw logging
          this.parser.on('data', (line: string) => {
            console.log(`[SerialHID][RAW ${new Date().toISOString()}] ${line}`);
            this.handleResponse(line);
          });

          this.port.on('error', (err) => {
            console.error('[SerialHID] Port error:', err && err.message ? err.message : err);
            this.isReady = false;
            this.scheduleReconnect();
          });

          this.port.on('close', () => {
            console.log('[SerialHID] Port closed');
            this.isReady = false;
            this.scheduleReconnect();
          });
        } catch (e) {
          lastError = e;
        }

        // Attempt to open
        const openResult = await new Promise<{ ok?: boolean; err?: any }>(res => {
          try {
            this.port!.open((err) => {
              if (err) return res({ err });
              return res({ ok: true });
            });
          } catch (e) {
            return res({ err: e });
          }
        });

        if (openResult.ok) {
          console.log('[SerialHID] Port opened successfully');

          // Wait for hello message from device (new protocol)
          const HELLO_TIMEOUT_MS = 3000; // Wait up to 3 seconds for hello
          let helloReceived = false;
          
          const helloTimeout = setTimeout(async () => {
            // Hello not received - try sending ping
            if (!helloReceived) {
              console.log('[SerialHID] Hello not received, sending ping...');
              try {
                await this.sendPing();
                // Wait for pong
                await new Promise<void>((resolvePong, rejectPong) => {
                  const pongTimeout = setTimeout(() => {
                    if (this.parser) this.parser.removeListener('data', checkPong);
                    rejectPong(new Error('Pong not received after ping'));
                  }, 2000);
                  
                  const checkPong = (line: string) => {
                    try {
                      const msg = JSON.parse(line) as any;
                      if (msg.type === 'pong') {
                        clearTimeout(pongTimeout);
                        if (this.parser) this.parser.removeListener('data', checkPong);
                        console.log('[SerialHID] Pong received, device is responsive');
                        this.isReady = true;
                        this.reconnectAttempts = 0; // Reset on successful connection
                        resolvePong();
                      }
                    } catch (e) {
                      // Ignore parse errors
                    }
                  };
                  
                  if (this.parser) this.parser.on('data', checkPong);
                });
              } catch (e: any) {
                console.error('[SerialHID] Ping/pong failed:', e.message);
                return reject(new Error('Device not responding to ping'));
              }
            }
          }, HELLO_TIMEOUT_MS);

          // Check for hello message
          const checkHello = (line: string) => {
            try {
              const msg = JSON.parse(line) as any;
              if (msg.type === 'hello' && msg.status === 'ready') {
                clearTimeout(helloTimeout);
                if (this.parser) this.parser.removeListener('data', checkHello);
                helloReceived = true;
                this.isReady = true;
                this.firmwareVersion = msg.firmwareVersion || 'unknown';
                this.reconnectAttempts = 0; // Reset on successful connection
                console.log(`[SerialHID] Device ready - Firmware v${this.firmwareVersion}`);
                resolve();
              }
            } catch (e) {
              // Ignore parse errors during startup
            }
          };

          if (this.parser) {
            this.parser.on('data', checkHello);
            // Also keep the hello listener active after timeout for late hellos
            setTimeout(() => {
              if (this.parser && helloReceived) {
                this.parser.removeListener('data', checkHello);
              }
            }, HELLO_TIMEOUT_MS + 2500);
          }

          // success — break out of attempts loop via resolve above
          return;
        } else {
          lastError = openResult.err;

          const msg = (lastError && lastError.message) ? lastError.message.toLowerCase() : '';
          const isAccessDenied = msg.includes('access denied') || msg.includes('permission') || msg.includes('busy') || (lastError && lastError.code === 'EACCES');

          if (attempt < MAX_OPEN_ATTEMPTS && isAccessDenied) {
            const backoff = BASE_BACKOFF_MS * Math.pow(2, attempt - 1);
            console.warn(`[SerialHID] Open attempt ${attempt} failed (${lastError.message}). Retrying after ${backoff}ms`);
            try {
              await this.disconnect();
            } catch (e) {
              // Ignore disconnect errors
            }
            await new Promise(r => setTimeout(r, backoff));
            continue;
          }

          // Not retrying (either non-retriable error or attempts exhausted)
          console.warn(`[SerialHID] Open attempt ${attempt} failed: ${lastError && lastError.message ? lastError.message : lastError}`);
          break;
        }
      }

      // If we reach here, all attempts failed
      reject(new Error(lastError && lastError.message ? lastError.message : 'Failed to open port'));
    });
  }
  
  /**
   * Schedule automatic reconnection with exponential backoff
   */
  private scheduleReconnect(): void {
    if (!this.autoReconnectEnabled) {
      console.log('[SerialHID] Auto-reconnect disabled, not reconnecting');
      return;
    }
    
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[SerialHID] Max reconnect attempts reached, giving up');
      return;
    }
    
    if (this.reconnectTimer) {
      return; // Already scheduled
    }
    
    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000 // Max 30 seconds
    );
    
    console.log(`[SerialHID] Scheduling reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
    
    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      try {
        console.log('[SerialHID] Attempting auto-reconnect...');
        await this.reconnect();
        console.log('[SerialHID] Auto-reconnect successful');
      } catch (e: any) {
        console.error('[SerialHID] Auto-reconnect failed:', e.message);
        // Will schedule another attempt via error handlers
      }
    }, delay);
  }
  
  /**
   * Send ping to device
   */
  private async sendPing(): Promise<void> {
    if (!this.port) {
      throw new Error('Port not open');
    }
    
    const pingMsg = JSON.stringify({ type: 'ping' }) + '\n';
    return new Promise((resolve, reject) => {
      this.port!.write(pingMsg, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }
  
  /**
   * Handle incoming response from device
   */
  private handleResponse(line: string): void {
    try {
      const response = JSON.parse(line) as any;
      
      // Handle control messages (type field)
      if (response.type === 'ack') {
        this.handleAck(response as AckMessage);
        return;
      }
      
      if (response.type === 'readyForNext') {
        this.deviceReady = true;
        return;
      }
      
      // Log errors from old-style responses
      if (response.status === 'error') {
        console.error(`[SerialHID] Device error: ${response.error} - ${response.msg}`);
      }
      
      // Call registered callback if exists (old-style responses)
      if (response.cmd) {
        const callback = this.responseCallbacks.get(response.cmd);
        if (callback) {
          callback(response);
          this.responseCallbacks.delete(response.cmd);
        }
      }
    } catch (e) {
      console.error('[SerialHID] Failed to parse response:', line);
    }
  }
  
  /**
   * Handle ACK message from device
   */
  private handleAck(ack: AckMessage): void {
    const commandId = ack.commandId;
    const inFlight = this.inFlightCommands.get(commandId);
    
    if (!inFlight) {
      console.warn(`[SerialHID] Received ACK for unknown command: ${commandId}`);
      return;
    }
    
    // Clear timeout
    clearTimeout(inFlight.timer);
    
    // Remove from in-flight tracking
    this.inFlightCommands.delete(commandId);
    
    // Resolve or reject based on status
    if (ack.status === 'ok') {
      inFlight.resolve(ack);
    } else {
      inFlight.reject(new Error(ack.message || 'Command failed'));
    }
  }
  
  /**
   * Send command to device with ACK tracking
   */
  async sendCommand(command: HIDCommand): Promise<HIDResponse | AckMessage> {
    if (!this.port || !this.isReady) {
      throw new Error('Device not ready. Call connect() first.');
    }
    
    // If ACK system is enabled, add command ID and use ACK tracking
    if (this.useAckSystem) {
      return this.sendCommandWithAck(command);
    }
    
    // Fallback to old-style response tracking
    return this.sendCommandLegacy(command);
  }
  
  /**
   * Send command with ACK-based tracking
   */
  private async sendCommandWithAck(command: HIDCommand): Promise<AckMessage> {
    // Generate unique command ID
    const commandId = randomUUID();
    
    // Add meta field with command ID
    const cmdWithMeta = {
      ...command,
      meta: {
        ...(command.meta || {}),
        commandId
      }
    };
    
    const cmdJson = JSON.stringify(cmdWithMeta) + '\n';
    let retryCount = 0;
    let timer: NodeJS.Timeout | null = null;
    
    return new Promise(async (resolve, reject) => {
      // Cleanup function to prevent memory leaks
      const cleanup = () => {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        this.inFlightCommands.delete(commandId);
      };
      
      const attemptSend = () => {
        // Clean up previous attempt's timer if it exists
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        
        // Set up timeout for this attempt
        timer = setTimeout(() => {
          cleanup();
          
          if (retryCount < this.maxRetries) {
            retryCount++;
            console.warn(`[SerialHID] Command timeout, retrying (${retryCount}/${this.maxRetries})`);
            attemptSend();
          } else {
            console.error(`[SerialHID] Command failed after ${this.maxRetries} retries`);
            this.isReady = false; // Mark device as unhealthy
            reject(new Error(`timed out`)); // Match test script expected error message
          }
        }, this.commandTimeout);
        
        // Track in-flight command with current state
        this.inFlightCommands.set(commandId, {
          commandId,
          command: cmdWithMeta,
          resolve: ((ack: AckMessage) => {
            cleanup();
            resolve(ack);
          }) as any,
          reject: (err: Error) => {
            cleanup();
            reject(err);
          },
          timer: timer!,
          retries: retryCount
        });
        
        // Send command - handle write errors immediately
        try {
          this.port!.write(cmdJson, (err) => {
            if (err) {
              cleanup();
              reject(new Error(`Failed to send command: ${err.message}`));
            }
          });
        } catch (err: any) {
          cleanup();
          reject(new Error(`Failed to send command: ${err.message}`));
        }
      };
      
      attemptSend();
    });
  }
  
  /**
   * Send command with legacy response tracking (backward compatibility)
   */
  private async sendCommandLegacy(command: HIDCommand): Promise<HIDResponse> {
    return new Promise((resolve, reject) => {
      const cmdJson = JSON.stringify(command) + '\n';
      
      // Register response callback
      const timeout = setTimeout(() => {
        this.responseCallbacks.delete(command.cmd);
        reject(new Error(`Command timeout: ${command.cmd}`));
      }, 2000);
      
      this.responseCallbacks.set(command.cmd, (response) => {
        clearTimeout(timeout);
        resolve(response);
      });
      
      // Send command
      this.port!.write(cmdJson, (err) => {
        if (err) {
          clearTimeout(timeout);
          this.responseCallbacks.delete(command.cmd);
          reject(new Error(`Failed to send command: ${err.message}`));
        }
      });
    });
  }
  
  /**
   * Check if device is connected and ready
   */
  isConnected(): boolean {
    return this.isReady && this.port !== null && this.port.isOpen;
  }
  
  /**
   * Close connection
   */
  async disconnect(): Promise<void> {
    // Clean up all in-flight commands to prevent memory leaks
    this.inFlightCommands.forEach((cmd) => {
      clearTimeout(cmd.timer);
      cmd.reject(new Error('Disconnected'));
    });
    this.inFlightCommands.clear();
    
    // Clear reconnect timer if present
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    // Remove all event listeners from parser
    if (this.parser) {
      this.parser.removeAllListeners();
      this.parser = null;
    }
    
    // Close and cleanup port
    if (this.port && this.port.isOpen) {
      return new Promise((resolve) => {
        // Remove all listeners before closing
        this.port!.removeAllListeners();
        this.port!.close(() => {
          console.log('[SerialHID] Disconnected');
          this.isReady = false;
          this.port = null;
          resolve();
        });
      });
    } else if (this.port) {
      // Port exists but not open, just clean it up
      this.port.removeAllListeners();
      this.port = null;
    }
  }
  
  /**
   * Attempt to reconnect
   */
  async reconnect(): Promise<void> {
    console.log('[SerialHID] Attempting reconnection...');
    await this.disconnect();
    await new Promise(resolve => setTimeout(resolve, 1000));
    await this.connect();
  }
}
