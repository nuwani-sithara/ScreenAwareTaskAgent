/**
 * Actuation Interface
 *
 * Provides a consistent interface for executing HID primitives.
 */

export interface ActuationResult {
  ok: boolean;
  error?: string;
}

export interface Actuator {
  readonly name: string;
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  isAvailable(): boolean;
  execute(command: any): Promise<void>;
}
