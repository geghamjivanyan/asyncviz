/**
 * Optional debug tracer for the websocket client.
 *
 * Off by default — when enabled (via ``localStorage.asyncviz.debug`` or
 * an explicit flag), the client routes every lifecycle transition and
 * envelope decision through this module. Output goes to a ring buffer
 * so the diagnostics page can show the last N events without writing
 * to the production console.
 */

import type { ConnectionPhase } from "@/runtime/websocket/lifecycle";

export type TraceEvent =
  | { kind: "phase"; from: ConnectionPhase; to: ConnectionPhase; at: number }
  | { kind: "frame"; type: string; sequence: number | null; at: number }
  | { kind: "reject"; reason: string; detail?: string; at: number }
  | { kind: "reconnect"; attempt: number; delayMs: number; at: number }
  | { kind: "hydrate"; lastSequence: number; runtimeId: string; at: number };

/** Same union as :type:`TraceEvent`, but ``at`` is optional — the
 *  diagnostics module stamps it when not provided. The discriminated
 *  union shape preserves TypeScript narrowing on ``.kind``. */
export type TraceEventInput =
  | { kind: "phase"; from: ConnectionPhase; to: ConnectionPhase; at?: number }
  | { kind: "frame"; type: string; sequence: number | null; at?: number }
  | { kind: "reject"; reason: string; detail?: string; at?: number }
  | { kind: "reconnect"; attempt: number; delayMs: number; at?: number }
  | { kind: "hydrate"; lastSequence: number; runtimeId: string; at?: number };

export interface DiagnosticsOptions {
  enabled?: boolean;
  capacity?: number;
  /** Test override; defaults to ``performance.now()``. */
  now?: () => number;
}

export class WebSocketDiagnostics {
  private _enabled: boolean;
  private _capacity: number;
  private _events: TraceEvent[] = [];
  private readonly _now: () => number;

  constructor(options: DiagnosticsOptions = {}) {
    this._enabled = options.enabled ?? false;
    this._capacity = options.capacity ?? 64;
    this._now = options.now ?? (() => performance.now());
  }

  setEnabled(enabled: boolean): void {
    this._enabled = enabled;
  }

  isEnabled(): boolean {
    return this._enabled;
  }

  record(event: TraceEventInput): void {
    if (!this._enabled) return;
    const stamped = { ...event, at: event.at ?? this._now() } as TraceEvent;
    this._events.push(stamped);
    while (this._events.length > this._capacity) {
      this._events.shift();
    }
  }

  events(): readonly TraceEvent[] {
    return [...this._events];
  }

  clear(): void {
    this._events = [];
  }
}
