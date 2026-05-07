/**
 * Local Actuator
 *
 * Executes HID commands locally using built-in Windows automation APIs.
 */

import { spawnSync } from 'child_process';
import { Actuator } from './actuator';
import { keycodeToKey } from '../transport/keycodes';

export class LocalActuator implements Actuator {
  readonly name: string = 'fallback';
  private initError: string | null = null;

  async connect(): Promise<void> {
    if (this.initError) return;

    if (process.platform !== 'win32') {
      this.initError = 'Local fallback actuator is only available on Windows';
      throw new Error(this.initError);
    }
  }

  async disconnect(): Promise<void> {
    // No persistent resources to release.
    return;
  }

  isAvailable(): boolean {
    return process.platform === 'win32' && this.initError === null;
  }

  async execute(command: any): Promise<void> {
    await this.connect();

    if (process.platform !== 'win32') {
      throw new Error(this.initError || 'Local actuator unavailable');
    }

    switch (command.cmd) {
      case 'mouse_move':
        this.moveMouseAbsolute(command.dx, command.dy);
        return;
      case 'mouse_click':
        this.mouseClick(command.button || 'left');
        return;
      case 'mouse_down':
        this.mouseToggle('down', command.button || 'left');
        return;
      case 'mouse_up':
        this.mouseToggle('up', command.button || 'left');
        return;
      case 'mouse_scroll':
        this.scrollMouse(command);
        return;
      case 'key_press':
        this.keyToggle(command.key, 'down');
        return;
      case 'key_release':
        if (command.key !== undefined) {
        this.keyToggle(command.key, 'up');
        }
        return;
      case 'key_combo':
        this.keyCombo(command);
        return;
      case 'type_text':
        this.typeString(command.text || '');
        return;
      case 'system':
        return;
      default:
        throw new Error(`Unsupported command for fallback: ${command.cmd}`);
    }
  }

  private moveMouseAbsolute(x: number, y: number): void {
    const size = this.getScreenSize();
    const clamped = this.clampToScreen(x, y, size.width, size.height);
    this.runPowerShell(`
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MouseNative {
  [DllImport("user32.dll")]
  public static extern bool SetCursorPos(int X, int Y);
}
"@
[MouseNative]::SetCursorPos(${clamped.x}, ${clamped.y}) | Out-Null
`);
  }

  private scrollMouse(command: any): void {
    const deltaX = Number.isFinite(command.deltaX) ? Math.round(command.deltaX) : 0;
    const deltaY = Number.isFinite(command.deltaY)
      ? Math.round(command.deltaY)
      : (Number.isFinite(command.scroll) ? Math.round(command.scroll) : 0);

    this.runPowerShell(`
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MouseNative {
  [DllImport("user32.dll")]
  public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
}
"@
$wheel = [uint32](${deltaY} * 120)
$hwheel = [uint32](${deltaX} * 120)
if ($wheel -ne 0) { [MouseNative]::mouse_event(0x0800, 0, 0, $wheel, [UIntPtr]::Zero) }
if ($hwheel -ne 0) { [MouseNative]::mouse_event(0x1000, 0, 0, $hwheel, [UIntPtr]::Zero) }
`);
  }

  private keyCombo(command: any): void {
    const modifiers: string[] = Array.isArray(command.modifiers)
      ? command.modifiers.map((m: string) => m.toLowerCase())
      : [];
    const key = typeof command.key === 'string' ? command.key.toLowerCase() : null;

    if (!key) {
      throw new Error('Invalid key_combo command');
    }

    for (const modifier of modifiers) {
      this.keyToggle(modifier, 'down');
    }

    this.keyToggle(key, 'down');
    this.keyToggle(key, 'up');

    for (const modifier of modifiers.slice().reverse()) {
      this.keyToggle(modifier, 'up');
    }
  }

  private keyToggle(keycodeOrName: number | string, direction: 'down' | 'up'): void {
    const key = this.resolveKeyName(keycodeOrName);
    const vk = this.keyNameToVirtualKey(key);
    const keyFlag = direction === 'down' ? 0x0000 : 0x0002;

    this.runPowerShell(`
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class KeyboardNative {
  [DllImport("user32.dll")]
  public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
}
"@
[KeyboardNative]::keybd_event(${vk}, 0, ${keyFlag}, [UIntPtr]::Zero)
`);
  }

  private typeString(text: string): void {
    const escaped = this.escapePowerShellSingleQuoted(this.escapeSendKeysText(text));
    this.runPowerShell(`
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait('${escaped}')
`);
  }

  private getScreenSize(): { width: number; height: number } {
    const output = this.runPowerShell(`
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class ScreenNative {
  [DllImport("user32.dll")]
  public static extern int GetSystemMetrics(int nIndex);
}
"@
"$([ScreenNative]::GetSystemMetrics(0)),$([ScreenNative]::GetSystemMetrics(1))"
`, true);

    const [widthText, heightText] = output.trim().split(',');
    const width = Number.parseInt(widthText, 10);
    const height = Number.parseInt(heightText, 10);

    if (!Number.isFinite(width) || !Number.isFinite(height)) {
      throw new Error('Failed to determine screen size for local actuator');
    }

    return { width, height };
  }

  private mouseClick(button: 'left' | 'right' | 'middle'): void {
    const { down, up } = this.mouseButtonFlags(button);
    this.runPowerShell(`
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MouseNative {
  [DllImport("user32.dll")]
  public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
}
"@
[MouseNative]::mouse_event(${down}, 0, 0, 0, [UIntPtr]::Zero)
[MouseNative]::mouse_event(${up}, 0, 0, 0, [UIntPtr]::Zero)
`);
  }

  private mouseToggle(direction: 'down' | 'up', button: 'left' | 'right' | 'middle'): void {
    const flag = this.mouseButtonFlags(button)[direction];
    this.runPowerShell(`
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MouseNative {
  [DllImport("user32.dll")]
  public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
}
"@
[MouseNative]::mouse_event(${flag}, 0, 0, 0, [UIntPtr]::Zero)
`);
  }

  private mouseButtonFlags(button: 'left' | 'right' | 'middle'): { down: number; up: number } {
    switch (button) {
      case 'right':
        return { down: 0x0008, up: 0x0010 };
      case 'middle':
        return { down: 0x0020, up: 0x0040 };
      case 'left':
      default:
        return { down: 0x0002, up: 0x0004 };
    }
  }

  private resolveKeyName(keycodeOrName: number | string): string {
    if (typeof keycodeOrName === 'number') {
      const mapped = keycodeToKey(keycodeOrName);
      if (!mapped) {
        throw new Error(`Unknown keycode: ${keycodeOrName}`);
      }
      return mapped;
    } else if (typeof keycodeOrName === 'string') {
      return keycodeOrName.toLowerCase();
    }

    throw new Error(`Unsupported key input: ${String(keycodeOrName)}`);
  }

  private clampToScreen(x: number, y: number, width: number, height: number): { x: number; y: number } {
    const clampedX = Math.max(0, Math.min(width - 1, Math.round(x)));
    const clampedY = Math.max(0, Math.min(height - 1, Math.round(y)));
    return { x: clampedX, y: clampedY };
  }

  private keyNameToVirtualKey(key: string): number {
    const normalized = key.toLowerCase();

    if (normalized.length === 1) {
      const charCode = normalized.charCodeAt(0);
      if (charCode >= 0x30 && charCode <= 0x39) return charCode;
      if (charCode >= 0x61 && charCode <= 0x7a) return charCode - 0x20;
      switch (normalized) {
        case ' ':
          return 0x20;
        case ',':
          return 0xBC;
        case '.':
          return 0xBE;
        case '/':
          return 0xBF;
        case ';':
          return 0xBA;
        case '\'':
          return 0xDE;
        case '[':
          return 0xDB;
        case ']':
          return 0xDD;
        case '\\':
          return 0xDC;
        case '-':
          return 0xBD;
        case '=':
          return 0xBB;
        case '`':
          return 0xC0;
      }
    }

    switch (normalized) {
      case 'enter':
      case 'return':
        return 0x0D;
      case 'escape':
      case 'esc':
        return 0x1B;
      case 'backspace':
        return 0x08;
      case 'tab':
        return 0x09;
      case 'space':
        return 0x20;
      case 'delete':
        return 0x2E;
      case 'insert':
        return 0x2D;
      case 'home':
        return 0x24;
      case 'end':
        return 0x23;
      case 'pageup':
        return 0x21;
      case 'pagedown':
        return 0x22;
      case 'left':
        return 0x25;
      case 'up':
        return 0x26;
      case 'right':
        return 0x27;
      case 'down':
        return 0x28;
      case 'capslock':
        return 0x14;
      case 'numlock':
        return 0x90;
      case 'scrolllock':
        return 0x91;
      case 'pause':
        return 0x13;
      case 'printscreen':
        return 0x2C;
      case 'control':
      case 'ctrl':
        return 0x11;
      case 'shift':
        return 0x10;
      case 'alt':
        return 0x12;
      case 'command':
      case 'meta':
      case 'win':
      case 'windows':
      case 'gui':
        return 0x5B;
      case 'f1':
        return 0x70;
      case 'f2':
        return 0x71;
      case 'f3':
        return 0x72;
      case 'f4':
        return 0x73;
      case 'f5':
        return 0x74;
      case 'f6':
        return 0x75;
      case 'f7':
        return 0x76;
      case 'f8':
        return 0x77;
      case 'f9':
        return 0x78;
      case 'f10':
        return 0x79;
      case 'f11':
        return 0x7A;
      case 'f12':
        return 0x7B;
      default:
        throw new Error(`Unsupported local key: ${key}`);
    }
  }

  private escapeSendKeysText(text: string): string {
    return text
      .replace(/~/g, '{~}')
      .replace(/\+/g, '{+}')
      .replace(/\^/g, '{^}')
      .replace(/%/g, '{%}')
      .replace(/\{/g, '{{}')
      .replace(/\}/g, '{}}')
      .replace(/\[/g, '{[}')
      .replace(/\]/g, '{]}');
  }

  private escapePowerShellSingleQuoted(text: string): string {
    return text.replace(/'/g, "''");
  }

  private runPowerShell(script: string, captureOutput = false): string {
    const result = spawnSync(
      'powershell.exe',
      ['-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
      {
        encoding: 'utf8',
        windowsHide: true,
        stdio: captureOutput ? ['ignore', 'pipe', 'pipe'] : ['ignore', 'pipe', 'pipe']
      }
    );

    if (result.error) {
      throw new Error(result.error.message);
    }

    if (result.status !== 0) {
      const stderr = (result.stderr || '').toString().trim();
      throw new Error(stderr || `PowerShell command failed with exit code ${result.status}`);
    }

    return (result.stdout || '').toString();
  }
}
