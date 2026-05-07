/**
 * Local Actuator
 *
 * Executes HID commands locally using OS-level APIs.
 */

import { Actuator } from './actuator';
import { keycodeToKey } from '../transport/keycodes';

type RobotJs = {
  getScreenSize: () => { width: number; height: number };
  moveMouse: (x: number, y: number) => void;
  moveMouseSmooth: (x: number, y: number) => void;
  mouseClick: (button?: 'left' | 'right' | 'middle', double?: boolean) => void;
  mouseToggle: (down?: 'down' | 'up', button?: 'left' | 'right' | 'middle') => void;
  scrollMouse: (x: number, y: number) => void;
  keyToggle: (key: string, down?: 'down' | 'up', modifiers?: string | string[]) => void;
  keyTap: (key: string, modifiers?: string | string[]) => void;
  typeString: (text: string) => void;
};

export class LocalActuator implements Actuator {
  readonly name: string = 'fallback';
  private robot: RobotJs | null = null;
  private initError: string | null = null;

  async connect(): Promise<void> {
    if (this.robot) return;

    // Try to load the native `robotjs` first; if it's not installed or fails
    // to build on the host (common on some Windows setups), fall back to
    // a lightweight shim that implements the same API with safe no-ops.
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const mod = require('robotjs');
      this.robot = mod as RobotJs;
      this.initError = null;
      return;
    } catch (err) {
      // Attempt to load local shim instead of crashing the whole server.
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const shim = require('./robotShim');
        this.robot = shim as RobotJs;
        this.initError = 'Using robotjs shim (robotjs not available)';
        return;
      } catch (shimErr: any) {
        this.initError = String(shimErr?.message || shimErr || 'Failed to load robotjs or shim');
        this.robot = null;
        // Do not throw here — callers will treat the actuator as unavailable.
        return;
      }
    }
  }

  async disconnect(): Promise<void> {
    // No persistent resources to release.
    return;
  }

  isAvailable(): boolean {
    return this.robot !== null;
  }

  async execute(command: any): Promise<void> {
    await this.connect();

    if (!this.robot) {
      throw new Error(this.initError || 'Local actuator unavailable');
    }

    switch (command.cmd) {
      case 'mouse_move':
        this.moveMouseAbsolute(command.dx, command.dy);
        return;
      case 'mouse_click':
        this.robot.mouseClick(command.button || 'left', false);
        return;
      case 'mouse_down':
        this.robot.mouseToggle('down', command.button || 'left');
        return;
      case 'mouse_up':
        this.robot.mouseToggle('up', command.button || 'left');
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
        this.robot.typeString(command.text || '');
        return;
      case 'system':
        return;
      default:
        throw new Error(`Unsupported command for fallback: ${command.cmd}`);
    }
  }

  private moveMouseAbsolute(x: number, y: number): void {
    const size = this.robot!.getScreenSize();
    const clamped = this.clampToScreen(x, y, size.width, size.height);
    this.robot!.moveMouse(clamped.x, clamped.y);
  }

  private scrollMouse(command: any): void {
    const deltaX = Number.isFinite(command.deltaX) ? Math.round(command.deltaX) : 0;
    const deltaY = Number.isFinite(command.deltaY)
      ? Math.round(command.deltaY)
      : (Number.isFinite(command.scroll) ? Math.round(command.scroll) : 0);

    this.robot!.scrollMouse(deltaX, deltaY);
  }

  private keyCombo(command: any): void {
    const modifiers: string[] = Array.isArray(command.modifiers)
      ? command.modifiers.map((m: string) => m.toLowerCase())
      : [];
    const key = typeof command.key === 'string' ? command.key.toLowerCase() : null;

    if (!key) {
      throw new Error('Invalid key_combo command');
    }

    this.robot!.keyTap(key, modifiers);
  }

  private keyToggle(keycodeOrName: number | string, direction: 'down' | 'up'): void {
    let key = '';

    if (typeof keycodeOrName === 'number') {
      const mapped = keycodeToKey(keycodeOrName);
      if (!mapped) {
        throw new Error(`Unknown keycode: ${keycodeOrName}`);
      }
      key = mapped;
    } else if (typeof keycodeOrName === 'string') {
      key = keycodeOrName.toLowerCase();
    }

    this.robot!.keyToggle(key, direction);
  }

  private clampToScreen(x: number, y: number, width: number, height: number): { x: number; y: number } {
    const clampedX = Math.max(0, Math.min(width - 1, Math.round(x)));
    const clampedY = Math.max(0, Math.min(height - 1, Math.round(y)));
    return { x: clampedX, y: clampedY };
  }
}
