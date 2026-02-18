/**
 * Structured Error Classes
 * 
 * Custom error classes for better error handling and debugging
 */

import { ErrorType } from './protocol';

/**
 * Base HID Error
 */
export class HIDError extends Error {
  public readonly code: ErrorType;
  public readonly timestamp: number;
  
  constructor(code: ErrorType, message: string) {
    super(message);
    this.name = 'HIDError';
    this.code = code;
    this.timestamp = Date.now();
    Error.captureStackTrace(this, this.constructor);
  }
}

/**
 * Device Not Ready Error
 */
export class DeviceNotReadyError extends HIDError {
  constructor(message: string = 'Device not ready') {
    super(ErrorType.DEVICE_NOT_READY, message);
    this.name = 'DeviceNotReadyError';
  }
}

/**
 * Connection Failed Error
 */
export class ConnectionFailedError extends HIDError {
  constructor(message: string = 'Connection failed') {
    super(ErrorType.CONNECTION_FAILED, message);
    this.name = 'ConnectionFailedError';
  }
}

/**
 * Command Timeout Error
 */
export class CommandTimeoutError extends HIDError {
  public readonly commandId?: string;
  public readonly retries: number;
  
  constructor(message: string, commandId?: string, retries: number = 0) {
    super(ErrorType.COMMAND_TIMEOUT, message);
    this.name = 'CommandTimeoutError';
    this.commandId = commandId;
    this.retries = retries;
  }
}

/**
 * Validation Error
 */
export class ValidationError extends HIDError {
  public readonly field?: string;
  public readonly value?: any;
  
  constructor(message: string, field?: string, value?: any) {
    super(ErrorType.INVALID_PARAM, message);
    this.name = 'ValidationError';
    this.field = field;
    this.value = value;
  }
}

/**
 * Protocol Error (parsing, invalid JSON, etc.)
 */
export class ProtocolError extends HIDError {
  public readonly rawData?: string;
  
  constructor(code: ErrorType, message: string, rawData?: string) {
    super(code, message);
    this.name = 'ProtocolError';
    this.rawData = rawData;
  }
}

/**
 * Device Execution Error
 */
export class ExecutionError extends HIDError {
  public readonly commandId?: string;
  public readonly deviceMessage?: string;
  
  constructor(message: string, commandId?: string, deviceMessage?: string) {
    super(ErrorType.INVALID_PARAM, message);
    this.name = 'ExecutionError';
    this.commandId = commandId;
    this.deviceMessage = deviceMessage;
  }
}
