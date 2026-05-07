// Lightweight shim that mimics a subset of robotjs API used by the app.
// This shim performs safe no-ops and logs warnings when actions are requested.

function warn(...args: any[]) {
  // Keep messages prefixed so logs are searchable.
  // eslint-disable-next-line no-console
  console.warn('[robotjs-shim]', ...args);
}

const shim = {
  getScreenSize(): { width: number; height: number } {
    // Return a sensible default. This can be overridden by the environment
    // if accurate screen size is required.
    return { width: 1920, height: 1080 };
  },

  moveMouse(x: number, y: number): void {
    warn('moveMouse called but robotjs is not available; no-op', x, y);
  },

  moveMouseSmooth(x: number, y: number): void {
    warn('moveMouseSmooth called but robotjs is not available; no-op', x, y);
  },

  mouseClick(button: 'left' | 'right' | 'middle' = 'left', double = false): void {
    warn('mouseClick called but robotjs is not available; no-op', button, double);
  },

  mouseToggle(down: 'down' | 'up' = 'down', button: 'left' | 'right' | 'middle' = 'left'): void {
    warn('mouseToggle called but robotjs is not available; no-op', down, button);
  },

  scrollMouse(x: number, y: number): void {
    warn('scrollMouse called but robotjs is not available; no-op', x, y);
  },

  keyToggle(key: string, down: 'down' | 'up' = 'down', modifiers?: string | string[]): void {
    warn('keyToggle called but robotjs is not available; no-op', key, down, modifiers);
  },

  keyTap(key: string, modifiers?: string | string[]): void {
    warn('keyTap called but robotjs is not available; no-op', key, modifiers);
  },

  typeString(text: string): void {
    warn('typeString called but robotjs is not available; no-op', text);
  }
};

// Export as CommonJS because callers use `require()`.
module.exports = shim;
