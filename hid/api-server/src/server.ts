/**
 * Production REST API Server for HID Control
 * 
 * Provides HTTP endpoints for external systems to control HID device
 * 
 * Endpoints:
 * - POST /hid/command - Execute HID command
 * - GET /hid/status - Get device status
 * - GET /health - Health check
 */

import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import { DeviceShadow } from '../../device-shadow/src/index';

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Global device shadow instance
let shadow: DeviceShadow | null = null;
let isConnecting = false;

/**
 * Initialize device shadow connection
 */
async function initializeDevice(): Promise<void> {
  if (shadow || isConnecting) return;
  
  isConnecting = true;
  console.log('[API] Initializing HID device connection...');
  
  try {
    shadow = new DeviceShadow();
    await shadow.connect();
    console.log('[API] HID device connected successfully');
  } catch (error: any) {
    console.error('[API] Failed to connect to HID device:', error.message);
    shadow = null;
  } finally {
    isConnecting = false;
  }
}

/**
 * Ensure device is connected
 */
async function ensureConnected(): Promise<void> {
  if (shadow && shadow.isConnected()) {
    return;
  }
  
  await initializeDevice();
  
  if (!shadow || !shadow.isConnected()) {
    throw new Error('Device not available');
  }
}

/**
 * POST /hid/command
 * Execute a HID command
 * 
 * Body:
 * {
 *   "type": "mouse_move" | "mouse_click" | "mouse_drag" | "mouse_scroll" | "key_combo" | "type_text",
 *   "payload": { ... command-specific parameters ... }
 * }
 * 
 * Examples:
 * {
 *   "type": "mouse_move",
 *   "payload": { "dx": 100, "dy": 50, "smooth": true }
 * }
 * 
 * {
 *   "type": "mouse_drag",
 *   "payload": { "dx": 200, "dy": 100, "button": "left", "duration": 500 }
 * }
 * 
 * {
 *   "type": "key_combo",
 *   "payload": { "modifiers": ["ctrl"], "key": "c" }
 * }
 */
app.post('/hid/command', async (req: Request, res: Response) => {
  try {
    // Validate request body
    const { type, payload } = req.body;
    
    if (!type || typeof type !== 'string') {
      return res.status(400).json({
        success: false,
        error: 'Missing or invalid "type" field'
      });
    }
    
    if (!payload || typeof payload !== 'object') {
      return res.status(400).json({
        success: false,
        error: 'Missing or invalid "payload" field'
      });
    }
    
    // Ensure device is connected
    try {
      await ensureConnected();
    } catch (error: any) {
      return res.status(503).json({
        success: false,
        error: 'Device offline',
        message: error.message
      });
    }
    
    // Construct command
    const command = {
      cmd: type,
      ...payload
    };
    
    // Execute command and wait for ACK
    const startTime = Date.now();
    try {
      await shadow!.executeCommand(command);
      const executionTime = Date.now() - startTime;
      
      return res.status(200).json({
        success: true,
        executionTime: `${executionTime}ms`
      });
    } catch (error: any) {
      console.error('[API] Command execution failed:', error.message);
      return res.status(500).json({
        success: false,
        error: 'Execution failed',
        message: error.message
      });
    }
  } catch (error: any) {
    console.error('[API] Unexpected error:', error);
    return res.status(500).json({
      success: false,
      error: 'Internal server error',
      message: error.message
    });
  }
});

/**
 * GET /hid/status
 * Get device status and statistics
 * 
 * Response:
 * {
 *   "connected": true,
 *   "firmwareVersion": "2.0.0",
 *   "portPath": "COM3",
 *   "uptime": 123456,
 *   "stats": {
 *     "totalCommands": 42,
 *     "successRate": 98.5,
 *     "uptime": 123456
 *   }
 * }
 */
app.get('/hid/status', async (req: Request, res: Response) => {
  try {
    if (!shadow) {
      await initializeDevice();
    }
    
    if (!shadow) {
      return res.status(200).json({
        connected: false,
        error: 'Device not initialized'
      });
    }
    
    const state = shadow.getState();
    const stats = shadow.getStats();
    
    return res.status(200).json({
      connected: shadow.isConnected(),
      firmwareVersion: state.connection.firmwareVersion || 'unknown',
      portPath: state.connection.devicePath || 'unknown',
      lastHeartbeat: state.connection.lastHeartbeat,
      uptime: state.connection.connectedSince 
        ? Date.now() - state.connection.connectedSince 
        : 0,
      stats: stats
    });
  } catch (error: any) {
    console.error('[API] Status check failed:', error);
    return res.status(500).json({
      success: false,
      error: 'Failed to get status',
      message: error.message
    });
  }
});

/**
 * GET /health
 * Health check endpoint
 */
app.get('/health', (req: Request, res: Response) => {
  return res.status(200).json({
    status: 'ok',
    service: 'HID API Server',
    version: '2.0.0',
    timestamp: new Date().toISOString()
  });
});

/**
 * GET /
 * API documentation
 */
app.get('/', (req: Request, res: Response) => {
  return res.status(200).json({
    service: 'HID API Server',
    version: '2.0.0',
    endpoints: {
      'POST /hid/command': 'Execute HID command',
      'GET /hid/status': 'Get device status',
      'GET /health': 'Health check'
    },
    documentation: 'https://github.com/your-repo/hid-api-server'
  });
});

/**
 * Error handling middleware
 */
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  console.error('[API] Unhandled error:', err);
  return res.status(500).json({
    success: false,
    error: 'Internal server error',
    message: err.message
  });
});

/**
 * Start server
 */
async function start() {
  // Initialize device connection on startup
  await initializeDevice();
  
  app.listen(PORT, () => {
    console.log(`[API] HID API Server running on port ${PORT}`);
    console.log(`[API] Health check: http://localhost:${PORT}/health`);
    console.log(`[API] Device status: http://localhost:${PORT}/hid/status`);
    console.log(`[API] Execute command: POST http://localhost:${PORT}/hid/command`);
  });
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('[API] Shutting down...');
  if (shadow) {
    await shadow.disconnect();
  }
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('[API] Shutting down...');
  if (shadow) {
    await shadow.disconnect();
  }
  process.exit(0);
});

// Start the server
start().catch((error) => {
  console.error('[API] Failed to start server:', error);
  process.exit(1);
});
