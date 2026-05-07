/**
 * HID API server
 *
 * This service owns mouse and keyboard execution for the project.
 * The backend sends commands here; this server performs the actual OS-level
 * input locally on the host machine.
 */

import express, { NextFunction, Request, Response } from 'express';
import cors from 'cors';
import { execFile } from 'child_process';
import { promisify } from 'util';

const app = express();
const PORT = Number(process.env.PORT || 3015);

app.use(cors());
app.use(express.json({ limit: '1mb' }));

const execFileAsync = promisify(execFile);

type ProxyCommandRequest = {
  type?: string;
  payload?: Record<string, any>;
};

const HID_TO_VK: Record<number, number> = {
  0x04: 0x41, 0x05: 0x42, 0x06: 0x43, 0x07: 0x44, 0x08: 0x45, 0x09: 0x46,
  0x0A: 0x47, 0x0B: 0x48, 0x0C: 0x49, 0x0D: 0x4A, 0x0E: 0x4B, 0x0F: 0x4C,
  0x10: 0x4D, 0x11: 0x4E, 0x12: 0x4F, 0x13: 0x50, 0x14: 0x51, 0x15: 0x52,
  0x16: 0x53, 0x17: 0x54, 0x18: 0x55, 0x19: 0x56, 0x1A: 0x57, 0x1B: 0x58,
  0x1C: 0x59, 0x1D: 0x5A,
  0x1E: 0x31, 0x1F: 0x32, 0x20: 0x33, 0x21: 0x34, 0x22: 0x35,
  0x23: 0x36, 0x24: 0x37, 0x25: 0x38, 0x26: 0x39, 0x27: 0x30,
  0x28: 0x0D,
  0x29: 0x1B,
  0x2A: 0x08,
  0x2B: 0x09,
  0x2C: 0x20,
  0x4A: 0x24,
  0x4B: 0x21,
  0x4C: 0x2E,
  0x4D: 0x23,
  0x4E: 0x22,
  0x4F: 0x27,
  0x50: 0x25,
  0x51: 0x28,
  0x52: 0x26,
  0xE0: 0xA2, // left ctrl
  0xE1: 0xA0, // left shift
  0xE2: 0xA4, // left alt
  0xE3: 0x5B, // left gui / win
};

function toVkCode(key: unknown): number | null {
  if (typeof key === 'number' && Number.isFinite(key)) {
    return HID_TO_VK[key] ?? null;
  }

  if (typeof key !== 'string') {
    return null;
  }

  const normalized = key.trim().toLowerCase();
  const named: Record<string, number> = {
    enter: 0x0D,
    return: 0x0D,
    tab: 0x09,
    escape: 0x1B,
    esc: 0x1B,
    backspace: 0x08,
    space: 0x20,
    delete: 0x2E,
    del: 0x2E,
    home: 0x24,
    end: 0x23,
    pageup: 0x21,
    pagedown: 0x22,
    up: 0x26,
    down: 0x28,
    left: 0x25,
    right: 0x27,
    ctrl: 0xA2,
    control: 0xA2,
    shift: 0xA0,
    alt: 0xA4,
    meta: 0x5B,
    win: 0x5B,
    cmd: 0x5B,
  };

  if (named[normalized] !== undefined) {
    return named[normalized];
  }

  if (normalized.length === 1) {
    const ch = normalized[0];
    if (/[a-z]/.test(ch)) return ch.toUpperCase().charCodeAt(0);
    if (/[0-9]/.test(ch)) return ch.charCodeAt(0);
  }

  return null;
}

function buildPsCommand(script: string): string {
  return [
    '$ErrorActionPreference = "Stop"',
    'Add-Type -AssemblyName System.Windows.Forms',
    "Add-Type -TypeDefinition @'",
    'using System;',
    'using System.Runtime.InteropServices;',
    'public static class NativeInput {',
    '  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);',
    '  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);',
    '  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);',
    '}',
    "'@",
    script,
  ].join('\r\n');
}

async function runPowerShell(script: string): Promise<void> {
  const fullScript = buildPsCommand(script);
  await execFileAsync('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', fullScript], {
    windowsHide: true,
  });
}

async function executeCommand(type: string, payload: Record<string, any>): Promise<void> {
  switch (type) {
    case 'mouse_move': {
      const x = Math.round(Number(payload.dx ?? 0));
      const y = Math.round(Number(payload.dy ?? 0));
      await runPowerShell(`[NativeInput]::SetCursorPos(${x}, ${y}) | Out-Null;`);
      return;
    }
    case 'mouse_click': {
      const button = String(payload.button || 'left').toLowerCase();
      const count = Math.max(1, Math.round(Number(payload.count ?? 1)));
      const downFlag = button === 'right' ? '0x0008' : button === 'middle' ? '0x0020' : '0x0002';
      const upFlag = button === 'right' ? '0x0010' : button === 'middle' ? '0x0040' : '0x0004';
      const script = Array.from({ length: count })
        .map(() => `[NativeInput]::mouse_event(${downFlag}, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 30; [NativeInput]::mouse_event(${upFlag}, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 30;`)
        .join(' ');
      await runPowerShell(script);
      return;
    }
    case 'mouse_down': {
      const button = String(payload.button || 'left').toLowerCase();
      const downFlag = button === 'right' ? '0x0008' : button === 'middle' ? '0x0020' : '0x0002';
      await runPowerShell(`[NativeInput]::mouse_event(${downFlag}, 0, 0, 0, [UIntPtr]::Zero);`);
      return;
    }
    case 'mouse_up': {
      const button = String(payload.button || 'left').toLowerCase();
      const upFlag = button === 'right' ? '0x0010' : button === 'middle' ? '0x0040' : '0x0004';
      await runPowerShell(`[NativeInput]::mouse_event(${upFlag}, 0, 0, 0, [UIntPtr]::Zero);`);
      return;
    }
    case 'mouse_scroll': {
      const deltaY = Number.isFinite(payload.deltaY) ? Math.round(Number(payload.deltaY)) : 0;
      const deltaX = Number.isFinite(payload.deltaX) ? Math.round(Number(payload.deltaX)) : 0;
      const scroll = Number.isFinite(payload.scroll) ? Math.round(Number(payload.scroll)) : 0;
      const vertical = deltaY || scroll;
      const parts: string[] = [];
      if (vertical) {
        parts.push(`[NativeInput]::mouse_event(0x0800, 0, 0, ${vertical * 120}, [UIntPtr]::Zero);`);
      }
      if (deltaX) {
        parts.push(`[NativeInput]::mouse_event(0x01000, 0, 0, ${deltaX * 120}, [UIntPtr]::Zero);`);
      }
      await runPowerShell(parts.join(' '));
      return;
    }
    case 'key_press':
    case 'key_release': {
      const vk = toVkCode(payload.key);
      if (vk === null) {
        throw new Error(`Unsupported key: ${String(payload.key)}`);
      }
      const flags = type === 'key_release' ? '0x0002' : '0x0000';
      await runPowerShell(`[NativeInput]::keybd_event(${vk}, 0, ${flags}, [UIntPtr]::Zero);`);
      return;
    }
    case 'key_combo': {
      const modifiers = Array.isArray(payload.modifiers) ? payload.modifiers : [];
      const modVks = modifiers.map(toVkCode).filter((v): v is number => v !== null);
      const keyVk = toVkCode(payload.key);
      if (keyVk === null) {
        throw new Error(`Unsupported key combo key: ${String(payload.key)}`);
      }
      const parts: string[] = [];
      for (const vk of modVks) {
        parts.push(`[NativeInput]::keybd_event(${vk}, 0, 0x0000, [UIntPtr]::Zero);`);
      }
      parts.push(`[NativeInput]::keybd_event(${keyVk}, 0, 0x0000, [UIntPtr]::Zero);`);
      parts.push(`[NativeInput]::keybd_event(${keyVk}, 0, 0x0002, [UIntPtr]::Zero);`);
      for (const vk of modVks.slice().reverse()) {
        parts.push(`[NativeInput]::keybd_event(${vk}, 0, 0x0002, [UIntPtr]::Zero);`);
      }
      await runPowerShell(parts.join(' '));
      return;
    }
    case 'type_text': {
      const text = String(payload.text ?? '');
      const encoded = Buffer.from(text, 'utf16le').toString('base64');
      await runPowerShell(
        `$text = [System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String('${encoded}'));` +
        `Set-Clipboard -Value $text; ` +
        `[NativeInput]::keybd_event(0x11, 0, 0x0000, [UIntPtr]::Zero); ` +
        `[NativeInput]::keybd_event(0x56, 0, 0x0000, [UIntPtr]::Zero); ` +
        `[NativeInput]::keybd_event(0x56, 0, 0x0002, [UIntPtr]::Zero); ` +
        `[NativeInput]::keybd_event(0x11, 0, 0x0002, [UIntPtr]::Zero);`
      );
      return;
    }
    case 'system':
      return;
    default:
      throw new Error(`Unsupported command: ${type}`);
  }
}

app.post('/hid/command', async (req: Request, res: Response) => {
  try {
    const body = req.body as ProxyCommandRequest;
    const type = body?.type;
    const payload = body?.payload;

    if (!type || typeof type !== 'string') {
      return res.status(400).json({ success: false, error: 'Missing or invalid "type" field' });
    }

    if (!payload || typeof payload !== 'object') {
      return res.status(400).json({ success: false, error: 'Missing or invalid "payload" field' });
    }

    const start = Date.now();
    await executeCommand(type, payload);
    return res.status(200).json({
      success: true,
      executionTime: `${Date.now() - start}ms`,
    });
  } catch (error: any) {
    console.error('[API] Command execution failed:', error);
    return res.status(500).json({
      success: false,
      error: 'Execution failed',
      message: error.message,
    });
  }
});

app.get('/hid/status', (_req: Request, res: Response) => {
  return res.status(200).json({
    connected: true,
    firmwareVersion: 'host-input',
    portPath: 'local-os-api',
    lastHeartbeat: Date.now(),
    uptime: 0,
    stats: {
      totalCommands: 0,
      successRate: 100,
      uptime: 0,
    },
  });
});

app.get('/health', (_req: Request, res: Response) => {
  return res.status(200).json({
    status: 'ok',
    service: 'HID API Server',
    timestamp: new Date().toISOString(),
  });
});

app.get('/', (_req: Request, res: Response) => {
  return res.status(200).json({
    service: 'HID API Server',
    endpoints: {
      'POST /hid/command': 'Execute HID command',
      'GET /hid/status': 'Get device status',
      'GET /health': 'Health check',
    },
  });
});

app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('[API] Unhandled error:', err);
  return res.status(500).json({
    success: false,
    error: 'Internal server error',
    message: err.message,
  });
});

app.listen(PORT, () => {
  console.log(`[API] HID API Server running on port ${PORT}`);
  console.log(`[API] Health check: http://localhost:${PORT}/health`);
  console.log(`[API] Device status: http://localhost:${PORT}/hid/status`);
});
