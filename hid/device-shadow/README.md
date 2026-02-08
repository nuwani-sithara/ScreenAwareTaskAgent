# Device Shadow Service

Local service that bridges high-level agent commands to ESP32-S3 HID device.

## Overview

The Device Shadow is an intelligent middleware layer that:
- Validates and sanitizes commands
- Normalizes commands into HID primitives
- Generates human-like mouse movements
- Manages command queue and timing
- Tracks execution state and statistics
- Handles auto-reconnection

## Installation

```bash
npm install
```

## Build

```bash
npm run build
```

## Usage

```typescript
import DeviceShadow from './src/index';

const shadow = new DeviceShadow();

// Connect to device
await shadow.connect();

// Execute commands
await shadow.executeCommand({
  cmd: 'mouse_move',
  dx: 100,
  dy: 50,
  smooth: true
});

await shadow.executeCommand({
  cmd: 'mouse_click',
  button: 'left'
});

// Get statistics
console.log(shadow.getStats());

// Disconnect
await shadow.disconnect();
```

## Architecture

```
DeviceShadow (index.ts)
├── Transport Layer
│   ├── validator.ts    - Command validation
│   ├── sanitizer.ts    - Safety constraints
│   └── normalizer.ts   - HID primitive conversion
├── Motion Engine
│   └── mouseEngine.ts  - Smooth movement generation
├── Queue
│   └── commandQueue.ts - Sequential execution
├── HID Interface
│   └── serialHID.ts    - USB CDC Serial communication
└── State Manager
    └── shadowState.ts  - Status tracking
```

## API Reference

### DeviceShadow

#### `connect(): Promise<void>`
Connect to ESP32-S3 device.

#### `executeCommand(command: any): Promise<void>`
Execute a high-level command.

#### `getState(): any`
Get current device state.

#### `getStats(): any`
Get execution statistics.

#### `isConnected(): boolean`
Check connection status.

#### `disconnect(): Promise<void>`
Disconnect from device.

## Command Format

See [../shared/protocol.md](../shared/protocol.md) for complete command reference.

### Basic Commands

```typescript
// Mouse move
{ cmd: 'mouse_move', dx: 10, dy: 5 }

// Mouse move (smooth)
{ cmd: 'mouse_move', dx: 200, dy: 100, smooth: true, duration: 500 }

// Mouse click
{ cmd: 'mouse_click', button: 'left' }

// Type text
{ cmd: 'type_text', text: 'Hello World' }

// Scroll
{ cmd: 'mouse_scroll', scroll: 3 }
```

## Development

### Running Tests

```bash
npm test
```

### Debug Mode

Enable verbose logging:

```typescript
const shadow = new DeviceShadow();
// Set log level to debug
```

## Troubleshooting

### Device Not Found

Ensure ESP32-S3 is connected and firmware is running.
Check VID/PID in [hid/serialHID.ts](src/hid/serialHID.ts).

### Connection Timeout

Increase timeout in `serialHID.ts` if device takes longer to initialize.

### Commands Failing

Check validation errors and ensure command format matches protocol specification.

## License

MIT
