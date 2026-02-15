/**
 * Protocol Types and Interfaces
 * 
 * Shared type definitions for HID command protocol
 */

// ============================================================================
// COMMAND TYPES
// ============================================================================

export enum CommandType {
  MOUSE_MOVE = 'mouse_move',
  MOUSE_CLICK = 'mouse_click',
  MOUSE_SCROLL = 'mouse_scroll',
  MOUSE_DRAG = 'mouse_drag',
  MOUSE_DOWN = 'mouse_down',
  MOUSE_UP = 'mouse_up',
  KEY_PRESS = 'key_press',
  KEY_RELEASE = 'key_release',
  KEY_COMBO = 'key_combo',
  TYPE_TEXT = 'type_text',
  SYSTEM = 'system'
}

// ============================================================================
// MESSAGE TYPES (Control messages)
// ============================================================================

export enum MessageType {
  HELLO = 'hello',
  PING = 'ping',
  PONG = 'pong',
  ACK = 'ack',
  READY_FOR_NEXT = 'readyForNext'
}

// ============================================================================
// MOUSE BUTTONS
// ============================================================================

export enum MouseButton {
  LEFT = 'left',
  RIGHT = 'right',
  MIDDLE = 'middle'
}

// ============================================================================
// STATUS CODES
// ============================================================================

export enum StatusCode {
  OK = 'ok',
  ERROR = 'error',
  READY = 'ready'
}

// ============================================================================
// COMMAND INTERFACES
// ============================================================================

export interface CommandMeta {
  commandId: string;
}

export interface BaseCommand {
  cmd: CommandType | string;
  meta?: CommandMeta;
}

export interface MouseMoveCommand extends BaseCommand {
  cmd: CommandType.MOUSE_MOVE;
  dx: number;
  dy: number;
  smooth?: boolean;
  duration?: number;
}

export interface MouseClickCommand extends BaseCommand {
  cmd: CommandType.MOUSE_CLICK;
  button: MouseButton | string;
}

export interface MouseScrollCommand extends BaseCommand {
  cmd: CommandType.MOUSE_SCROLL;
  scroll?: number;  // Legacy format
  deltaX?: number;
  deltaY?: number;
}

export interface MouseDragCommand extends BaseCommand {
  cmd: CommandType.MOUSE_DRAG;
  dx: number;
  dy: number;
  button?: MouseButton | string;
  duration?: number;
}

export interface MouseDownCommand extends BaseCommand {
  cmd: CommandType.MOUSE_DOWN;
  button: MouseButton | string;
}

export interface MouseUpCommand extends BaseCommand {
  cmd: CommandType.MOUSE_UP;
  button?: MouseButton | string;
}

export interface KeyPressCommand extends BaseCommand {
  cmd: CommandType.KEY_PRESS;
  key: number;  // HID keycode
}

export interface KeyReleaseCommand extends BaseCommand {
  cmd: CommandType.KEY_RELEASE;
  key?: number;  // HID keycode (optional - releases all if omitted)
}

export interface KeyComboCommand extends BaseCommand {
  cmd: CommandType.KEY_COMBO;
  modifiers: string[];
  key: string;
}

export interface TypeTextCommand extends BaseCommand {
  cmd: CommandType.TYPE_TEXT;
  text: string;
}

export interface SystemCommand extends BaseCommand {
  cmd: CommandType.SYSTEM;
  code: number;
}

export type HIDCommand = 
  | MouseMoveCommand
  | MouseClickCommand
  | MouseScrollCommand
  | MouseDragCommand
  | MouseDownCommand
  | MouseUpCommand
  | KeyPressCommand
  | KeyReleaseCommand
  | KeyComboCommand
  | TypeTextCommand
  | SystemCommand;

// ============================================================================
// MESSAGE INTERFACES
// ============================================================================

export interface HelloMessage {
  type: MessageType.HELLO;
  status: StatusCode.READY;
  firmwareVersion: string;
}

export interface PingMessage {
  type: MessageType.PING;
}

export interface PongMessage {
  type: MessageType.PONG;
}

export interface AckMessage {
  type: MessageType.ACK;
  commandId: string;
  status: StatusCode.OK | StatusCode.ERROR;
  message?: string;
}

export interface ReadyForNextMessage {
  type: MessageType.READY_FOR_NEXT;
}

export type ControlMessage = 
  | HelloMessage
  | PingMessage
  | PongMessage
  | AckMessage
  | ReadyForNextMessage;

// ============================================================================
// RESPONSE INTERFACES
// ============================================================================

export interface SuccessResponse {
  status: StatusCode.OK;
  cmd: string;
}

export interface ErrorResponse {
  status: StatusCode.ERROR;
  error: string;
  msg: string;
}

export type HIDResponse = SuccessResponse | ErrorResponse;

// ============================================================================
// ERROR TYPES
// ============================================================================

export enum ErrorType {
  INVALID_JSON = 'invalid_json',
  MISSING_CMD = 'missing_cmd',
  UNKNOWN_CMD = 'unknown_cmd',
  MISSING_PARAM = 'missing_param',
  INVALID_PARAM = 'invalid_param',
  LINE_TOO_LONG = 'line_too_long',
  DEVICE_NOT_READY = 'device_not_ready',
  COMMAND_TIMEOUT = 'command_timeout',
  CONNECTION_FAILED = 'connection_failed'
}

// ============================================================================
// DEVICE STATE INTERFACES
// ============================================================================

export interface DeviceCapabilities {
  mouse: boolean;
  keyboard: boolean;
  consumer: boolean;
}

export interface ExecutionState {
  lastCommand: HIDCommand | null;
  lastCommandTime: number | null;
  lastCommandStatus: StatusCode.OK | StatusCode.ERROR | null;
  lastError: string | null;
  commandsExecuted: number;
  commandsFailed: number;
}

export interface ConnectionState {
  connected: boolean;
  devicePath: string | null;
  firmwareVersion: string | null;
  connectedSince: number | null;
  lastHeartbeat: number | null;
  reconnectAttempts: number;
}

export interface DeviceState {
  capabilities: DeviceCapabilities;
  execution: ExecutionState;
  connection: ConnectionState;
}
