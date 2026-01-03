import { SerialPort } from 'serialport';
import { ReadlineParser } from '@serialport/parser-readline';
import fs from 'fs';
import path from 'path';

/**
 * SerialHID - USB CDC Serial interface to ESP32-S3 HID device
 * 
 * Manages:
 * - Device discovery and connection
 * - Command transmission
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

export interface HIDCommand {
  cmd: string;
  [key: string]: any;
}

export class SerialHID {
  private port: SerialPort | null = null;
  private parser: ReadlineParser | null = null;
  private portPath: string | null = null;
  private isReady: boolean = false;
  private responseCallbacks: Map<string, (response: HIDResponse) => void> = new Map();
  
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
          if (this.port && this.port.isOpen) {
            try { this.port.close(() => {}); } catch (e) {}
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

          // Raw logging
          this.parser.on('data', (line: string) => {
            console.log(`[SerialHID][RAW ${new Date().toISOString()}] ${line}`);
            this.handleResponse(line);
          });

          this.port.on('error', (err) => {
            console.error('[SerialHID] Port error:', err && err.message ? err.message : err);
            this.isReady = false;
          });

          this.port.on('close', () => {
            console.log('[SerialHID] Port closed');
            this.isReady = false;
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

          // Wait for ready message from device
          const READY_TIMEOUT_MS = 15000; // allow firmware boot time
          const readyTimeout = setTimeout(() => {
            // remove ready checker and reject
            if (this.parser) this.parser.removeListener('data', checkReady);
            lastError = new Error('Device did not send ready signal within timeout');
            return reject(lastError);
          }, READY_TIMEOUT_MS);

          // Treat the first valid JSON response as a readiness signal.
          const checkReady = (line: string) => {
            try {
              const response = JSON.parse(line) as HIDResponse;
              clearTimeout(readyTimeout);
              if (this.parser) this.parser.removeListener('data', checkReady);
              this.isReady = true;
              console.log('[SerialHID] Device ready (first valid JSON):', response);
              resolve();
            } catch (e) {
              // Ignore parse errors during startup
            }
          };

          if (this.parser) this.parser.on('data', checkReady);

          // success — break out of attempts loop via resolve above
          return;
        } else {
          lastError = openResult.err;

          const msg = (lastError && lastError.message) ? lastError.message.toLowerCase() : '';
          const isAccessDenied = msg.includes('access denied') || msg.includes('permission') || msg.includes('busy') || (lastError && lastError.code === 'EACCES');

          if (attempt < MAX_OPEN_ATTEMPTS && isAccessDenied) {
            const backoff = BASE_BACKOFF_MS * Math.pow(2, attempt - 1);
            console.warn(`[SerialHID] Open attempt ${attempt} failed (${lastError.message}). Retrying after ${backoff}ms`);
            // cleanup before retry
            try { this.port.close(() => {}); } catch (e) {}
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
   * Handle incoming response from device
   */
  private handleResponse(line: string): void {
    try {
      const response = JSON.parse(line) as HIDResponse;
      
      // Log errors
      if (response.status === 'error') {
        console.error(`[SerialHID] Device error: ${response.error} - ${response.msg}`);
      }
      
      // Call registered callback if exists
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
   * Send command to device
   */
  async sendCommand(command: HIDCommand): Promise<HIDResponse> {
    if (!this.port || !this.isReady) {
      throw new Error('Device not ready. Call connect() first.');
    }
    
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
    if (this.port && this.port.isOpen) {
      return new Promise((resolve) => {
        this.port!.close(() => {
          console.log('[SerialHID] Disconnected');
          this.isReady = false;
          resolve();
        });
      });
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
