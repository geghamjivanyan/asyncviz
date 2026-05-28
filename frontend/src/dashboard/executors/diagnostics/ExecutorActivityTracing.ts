/**
 * Bounded ring buffer for executor activity render diagnostics.
 */

const CAPACITY = 256;

export type ExecutorActivityTraceKind =
  | "snapshot-fetched"
  | "snapshot-failed"
  | "ws-payload-applied"
  | "ws-payload-dropped"
  | "panel-rendered"
  | "overlay-rendered"
  | "selection-changed"
  | "inspector-revealed";

export interface ExecutorActivityTraceEntry {
  kind: ExecutorActivityTraceKind;
  detail: string;
  at: number;
}

let _enabled = false;
const _ring: ExecutorActivityTraceEntry[] = [];

export function isExecutorActivityTraceEnabled(): boolean { return _enabled; }

export function setExecutorActivityTraceEnabled(enabled: boolean): void {
  _enabled = enabled;
  if (!enabled) _ring.length = 0;
}

export function recordExecutorActivityTrace(
  entry: Omit<ExecutorActivityTraceEntry, "at">,
): void {
  if (!_enabled) return;
  _ring.push({ ...entry, at: Date.now() });
  if (_ring.length > CAPACITY) _ring.splice(0, _ring.length - CAPACITY);
}

export function getExecutorActivityTrace(): ReadonlyArray<ExecutorActivityTraceEntry> {
  return [..._ring];
}

export function clearExecutorActivityTrace(): void { _ring.length = 0; }
