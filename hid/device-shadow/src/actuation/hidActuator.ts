/**
 * HID Actuator
 *
 * Wraps the SerialHID transport as the primary actuator.
 */

import { SerialHID, HIDCommand, AckMessage, HIDResponse } from '../hid/serialHID';
import { Actuator } from './actuator';

export class HIDActuator implements Actuator {
  readonly name: string = 'hid';
  private readonly hid: SerialHID;

  constructor(hid?: SerialHID, onHeartbeat?: () => void) {
    this.hid = hid || new SerialHID();
    if (onHeartbeat) {
      this.hid.setHeartbeatCallback(onHeartbeat);
    }
  }

  async connect(): Promise<void> {
    await this.hid.connect();
  }

  async disconnect(): Promise<void> {
    await this.hid.disconnect();
  }

  isAvailable(): boolean {
    return this.hid.isConnected();
  }

  getFirmwareVersion(): string | null {
    return this.hid.getFirmwareVersion();
  }

  getPortPath(): string | null {
    return this.hid.getPortPath();
  }

  async execute(command: HIDCommand): Promise<void> {
    await this.hid.sendCommand(command);
  }

  async reconnect(): Promise<void> {
    await this.hid.reconnect();
  }

  getTransport(): SerialHID {
    return this.hid;
  }
}
