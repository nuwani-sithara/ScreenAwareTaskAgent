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

import express = require('express');
import { Request, Response, NextFunction } from 'express';
import cors = require('cors');
import * as fs from 'fs';
import * as path from 'path';
import { spawnSync } from 'child_process';

const app = express();
const PORT = process.env.PORT || 3015;
const SERVER_START_TIME = Date.now();
const PY_HELPER = String.raw`
import ctypes
import json
import platform
import shutil
import sys
import time

try:
  import pyautogui
  pyautogui.FAILSAFE = False
  pyautogui.PAUSE = 0.01
except Exception:
  pyautogui = None

WINDOWS = platform.system().lower().startswith("win")

HID_KEY_MAP = {
  0x28: "enter",
  0x29: "esc",
  0x2A: "backspace",
  0x2B: "tab",
  0x2C: "space",
  0x4C: "delete",
  0x4F: "right",
  0x50: "left",
  0x51: "down",
  0x52: "up",
  0x3A: "f1",
  0x3B: "f2",
  0x3C: "f3",
  0x3D: "f4",
  0x3E: "f5",
  0x3F: "f6",
  0x40: "f7",
  0x41: "f8",
  0x42: "f9",
  0x43: "f10",
  0x44: "f11",
  0x45: "f12",
}

if WINDOWS:
  user32 = ctypes.windll.user32
  MOUSEEVENTF_LEFTDOWN = 0x0002
  MOUSEEVENTF_LEFTUP = 0x0004
  MOUSEEVENTF_RIGHTDOWN = 0x0008
  MOUSEEVENTF_RIGHTUP = 0x0010
  MOUSEEVENTF_MIDDLEDOWN = 0x0020
  MOUSEEVENTF_MIDDLEUP = 0x0040
  MOUSEEVENTF_WHEEL = 0x0800
  MOUSEEVENTF_HWHEEL = 0x01000
  KEYEVENTF_KEYUP = 0x0002

  KEYBD_MAP = {
    "enter": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "tab": 0x09,
    "space": 0x20,
    "delete": 0x2E,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
  }

  def _key_down(vk):
    user32.keybd_event(vk, 0, 0, 0)

  def _key_up(vk):
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _normalize_key(value):
  if isinstance(value, int):
    value = HID_KEY_MAP.get(value, value)
  if not isinstance(value, str):
    return None
  value = value.strip().lower()
  return HID_KEY_MAP.get(int(value, 16), value) if value.startswith("0x") else value


def _move(x, y, duration=0):
  # Support both absolute (x,y) and relative (dx,dy) motion.
  # If caller provided dx/dy instead of x/y, treat as relative move.
  # Accept both int-like strings and numbers.
  if isinstance(x, (int, float)) and isinstance(y, (int, float)):
    # absolute move
    if pyautogui:
      pyautogui.moveTo(int(x), int(y), duration=max(float(duration or 0), 0))
      return
    if WINDOWS:
      user32.SetCursorPos(int(x), int(y))
      return
    raise RuntimeError("No mouse backend available")

  # Treat as relative move (dx/dy)
  dx = int(x or 0)
  dy = int(y or 0)
  if pyautogui:
    pyautogui.moveRel(dx, dy, duration=max(float(duration or 0), 0))
    return
  if WINDOWS:
    # Get current cursor position and add deltas
    class POINT(ctypes.Structure):
      _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    if not hasattr(user32, 'GetCursorPos'):
      raise RuntimeError("GetCursorPos not available on this platform")
    user32.GetCursorPos(ctypes.byref(pt))
    user32.SetCursorPos(int(pt.x + dx), int(pt.y + dy))
    return
  raise RuntimeError("No mouse backend available")


def _move_rel(dx, dy, duration=0):
  """
  Explicit relative move helper. Use this when the payload contained
  'dx'/'dy' keys (relative deltas) rather than absolute 'x'/'y'.
  """
  if pyautogui:
    pyautogui.moveRel(int(dx or 0), int(dy or 0), duration=max(float(duration or 0), 0))
    return
  if WINDOWS:
    class POINT(ctypes.Structure):
      _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    if not hasattr(user32, 'GetCursorPos'):
      raise RuntimeError("GetCursorPos not available on this platform")
    user32.GetCursorPos(ctypes.byref(pt))
    user32.SetCursorPos(int(pt.x + int(dx or 0)), int(pt.y + int(dy or 0)))
    return
  raise RuntimeError("No mouse backend available")


def _click(button="left", clicks=1, interval=0, x=None, y=None):
  # Allow absolute click via x/y or relative click via dx/dy by passing
  # deltas in x/y parameters. If x/y provided, move before clicking.
  if x is not None and y is not None:
    _move(x, y)

  if pyautogui:
    pyautogui.click(button=button, clicks=int(clicks or 1), interval=float(interval or 0))
    return
  if not WINDOWS:
    raise RuntimeError("No click backend available")
  down_up = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
  }.get(button.lower(), (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP))
  for _ in range(int(clicks or 1)):
    user32.mouse_event(down_up[0], 0, 0, 0, 0)
    user32.mouse_event(down_up[1], 0, 0, 0, 0)
    if interval:
      time.sleep(float(interval))


def _scroll(delta_y=0, delta_x=0):
  # Accept many common parameter names from different clients.
  dy = int(delta_y or 0)
  dx = int(delta_x or 0)
  if pyautogui:
    if dy:
      pyautogui.scroll(dy)
    if dx and hasattr(pyautogui, "hscroll"):
      pyautogui.hscroll(dx)
    return
  if WINDOWS:
    if dy:
      user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(dy * 120), 0)
    if dx:
      user32.mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, int(dx * 120), 0)
    return
  raise RuntimeError("No scroll backend available")


def _type_text(text, interval=0):
  if pyautogui:
    pyautogui.write(str(text or ""), interval=float(interval or 0))
    return
  raise RuntimeError("Typing requires pyautogui")


def _press_key(key):
  key_name = _normalize_key(key)
  if not key_name:
    raise RuntimeError(f"Unsupported key: {key}")
  if pyautogui:
    pyautogui.press(key_name)
    return
  if not WINDOWS:
    raise RuntimeError("Key press requires pyautogui")
  vk = KEYBD_MAP.get(key_name)
  if vk is None:
    raise RuntimeError(f"Unsupported key: {key_name}")
  _key_down(vk)
  _key_up(vk)


def _hotkey(modifiers, key):
  mods = [_normalize_key(m) for m in (modifiers or []) if _normalize_key(m)]
  key_name = _normalize_key(key)
  if pyautogui:
    pyautogui.hotkey(*(mods + ([key_name] if key_name else [])))
    return
  raise RuntimeError("Hotkey requires pyautogui")


def main():
  payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
  command = payload.get("cmd") or payload.get("type")
  body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload

  if command == "mouse_move":
    # Distinguish absolute vs relative moves by key presence.
    if "dx" in body or "dy" in body:
      dx = body.get("dx", 0)
      dy = body.get("dy", 0)
      _move_rel(dx, dy, body.get("duration", 0))
    else:
      x = body.get("x")
      y = body.get("y")
      if x is None or y is None:
        raise RuntimeError("mouse_move requires x/y or dx/dy")
      _move(x, y, body.get("duration", 0))
  elif command == "mouse_click":
    _click(
      button=str(body.get("button", "left")),
      clicks=body.get("clicks", 1),
      interval=body.get("interval", 0),
      x=body.get("x", body.get("dx")),
      y=body.get("y", body.get("dy")),
    )
  elif command == "mouse_scroll":
    # Normalize common scroll parameter names
    scroll_val = body.get("deltaY", body.get("scrollY", body.get("scroll", 0)))
    scroll_x = body.get("deltaX", body.get("scrollX", 0))
    _scroll(scroll_val, scroll_x)
  elif command == "type_text":
    _type_text(body.get("text", ""), body.get("interval", 0))
  elif command == "key_press":
    _press_key(body.get("key"))
  elif command == "key_combo":
    _hotkey(body.get("modifiers", []), body.get("key"))
  elif command == "mouse_drag":
    # Support both absolute drag-to and relative drag-by (dx/dy).
    if body.get("x") is not None and body.get("y") is not None:
      if pyautogui:
        pyautogui.dragTo(int(body["x"]), int(body["y"]), duration=float(body.get("duration", 0) or 0), button=str(body.get("button", "left")))
      else:
        raise RuntimeError("mouse_drag requires pyautogui for absolute drag")
    elif body.get("dx") is not None or body.get("dy") is not None:
      dx = int(body.get("dx", 0))
      dy = int(body.get("dy", 0))
      if pyautogui:
        pyautogui.dragRel(dx, dy, duration=float(body.get("duration", 0) or 0), button=str(body.get("button", "left")))
      else:
        raise RuntimeError("mouse_drag requires pyautogui for relative drag")
    else:
      raise RuntimeError("mouse_drag requires x/y or dx/dy")
  elif command == "wait":
    time.sleep(float(body.get("duration", body.get("duration_ms", 0)) or 0) / 1000.0)
  else:
    raise RuntimeError(f"Unsupported command: {command}")

  print(json.dumps({"success": True, "backend": "software", "command": command}))


if __name__ == "__main__":
  main()
`;

// Middleware
app.use(cors());
app.use(express.json());

let pythonExecutable: string | null = null;
let executorInitialized = false;

/**
 * Resolve a usable Python interpreter.
 */
function resolvePythonExecutable(): string | null {
  const candidates = [
    process.env.PYTHON,
    process.env.PYTHON_EXECUTABLE,
    path.resolve(__dirname, '..', '..', '..', 'backend', 'venv', 'Scripts', 'python.exe'),
    path.resolve(__dirname, '..', '..', '..', 'backend', '.venv', 'Scripts', 'python.exe'),
    'python',
    'py',
    'python3',
  ].filter((item): item is string => Boolean(item));

  const probe = (candidate: string, requirePyAutoGui: boolean): boolean => {
    if (path.isAbsolute(candidate) && !fs.existsSync(candidate)) {
      return false;
    }
    const script = requirePyAutoGui
      ? 'import pyautogui, sys; print(sys.executable)'
      : 'import sys; print(sys.executable)';
    const result = spawnSync(candidate, ['-c', script], {
      encoding: 'utf8',
      windowsHide: true,
    });
    return !result.error && result.status === 0;
  };

  for (const candidate of candidates) {
    if (probe(candidate, true)) {
      return candidate;
    }
  }

  for (const candidate of candidates) {
    if (probe(candidate, false)) {
      return candidate;
    }
  }

  return null;
}

/**
 * Initialize the software executor.
 */
async function initializeDevice(): Promise<void> {
  if (executorInitialized) {
    return;
  }

  pythonExecutable = resolvePythonExecutable();
  if (!pythonExecutable) {
    throw new Error('No Python interpreter available for software input execution');
  }

  executorInitialized = true;
  console.log(`[API] Software HID executor ready via ${pythonExecutable}`);
}

/**
 * Ensure the software executor is ready.
 */
async function ensureConnected(): Promise<void> {
  if (!executorInitialized) {
    await initializeDevice();
  }
  if (!pythonExecutable) {
    throw new Error('Software executor not available');
  }
}

function executeSoftwareCommand(command: Record<string, any>): void {
  if (!pythonExecutable) {
    throw new Error('Software executor not initialized');
  }

  const result = spawnSync(pythonExecutable, ['-c', PY_HELPER, JSON.stringify(command)], {
    encoding: 'utf8',
    windowsHide: true,
    maxBuffer: 1024 * 1024,
  });

  if (result.error) {
    throw new Error(result.error.message);
  }

  if (result.status !== 0) {
    const stderr = (result.stderr || '').trim();
    const stdout = (result.stdout || '').trim();
    throw new Error(stderr || stdout || `Executor failed with code ${result.status}`);
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
    
    // Ensure software executor is ready
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
    
    // Execute command via the software input layer
    const startTime = Date.now();
    try {
      executeSoftwareCommand(command);
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
    if (!executorInitialized) {
      await initializeDevice();
    }

    return res.status(200).json({
      connected: true,
      mode: 'software',
      backend: 'software',
      interpreter: pythonExecutable || 'unknown',
      firmwareVersion: 'software',
      portPath: 'local',
      lastHeartbeat: new Date().toISOString(),
      uptime: Date.now() - SERVER_START_TIME,
      stats: {
        totalCommands: 'n/a',
        successRate: 'n/a',
        uptime: Date.now() - SERVER_START_TIME,
      }
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
  // Start HTTP server immediately
  app.listen(PORT, () => {
    console.log(`[API] Software HID API Server running on port ${PORT}`);
    console.log(`[API] Health check: http://localhost:${PORT}/health`);
    console.log(`[API] Device status: http://localhost:${PORT}/hid/status`);
  });

  // Warm up the software executor in the background
  initializeDevice().catch((error) => {
    console.error('[API] Initial executor setup failed:', error.message);
  });
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('[API] Shutting down...');
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('[API] Shutting down...');
  process.exit(0);
});

// Start the server
start().catch((error) => {
  console.error('[API] Failed to start server:', error);
  process.exit(1);
});
