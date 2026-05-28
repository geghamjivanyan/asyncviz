/**
 * Bounded ring buffer for queue-pressure render diagnostics.
 *
 * Off by default; turned on by ``setQueuePressureTraceEnabled(true)``
 * when chasing a render-timing or selection-routing bug. The Diagnostics
 * page exposes a tail of recent entries.
 */

const CAPACITY = 256;

export type QueuePressureTraceKind =
  | "snapshot-fetched"
  | "snapshot-failed"
  | "ws-payload-applied"
  | "ws-payload-dropped"
  | "panel-rendered"
  | "overlay-rendered"
  | "selection-changed"
  | "inspector-revealed";

export interface QueuePressureTraceEntry {
  kind: QueuePressureTraceKind;
  detail: string;
  at: number;
}

let _enabled = false;
const _ring: QueuePressureTraceEntry[] = [];

export function isQueuePressureTraceEnabled(): boolean {
  return _enabled;
}

export function setQueuePressureTraceEnabled(enabled: boolean): void {
  _enabled = enabled;
  if (!enabled) _ring.length = 0;
}

export function recordQueuePressureTrace(entry: Omit<QueuePressureTraceEntry, "at">): void {
  if (!_enabled) return;
  _ring.push({ ...entry, at: Date.now() });
  if (_ring.length > CAPACITY) _ring.splice(0, _ring.length - CAPACITY);
}

export function getQueuePressureTrace(): ReadonlyArray<QueuePressureTraceEntry> {
  return [..._ring];
}

export function clearQueuePressureTrace(): void {
  _ring.length = 0;
}
