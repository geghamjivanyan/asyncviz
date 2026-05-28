/**
 * Bounded ring buffer for semaphore-contention render diagnostics.
 *
 * Off by default. The Diagnostics page exposes a tail of recent
 * entries when enabled.
 */

const CAPACITY = 256;

export type SemaphoreContentionTraceKind =
  | "snapshot-fetched"
  | "snapshot-failed"
  | "ws-payload-applied"
  | "ws-payload-dropped"
  | "panel-rendered"
  | "overlay-rendered"
  | "selection-changed"
  | "inspector-revealed";

export interface SemaphoreContentionTraceEntry {
  kind: SemaphoreContentionTraceKind;
  detail: string;
  at: number;
}

let _enabled = false;
const _ring: SemaphoreContentionTraceEntry[] = [];

export function isSemaphoreContentionTraceEnabled(): boolean {
  return _enabled;
}

export function setSemaphoreContentionTraceEnabled(enabled: boolean): void {
  _enabled = enabled;
  if (!enabled) _ring.length = 0;
}

export function recordSemaphoreContentionTrace(
  entry: Omit<SemaphoreContentionTraceEntry, "at">,
): void {
  if (!_enabled) return;
  _ring.push({ ...entry, at: Date.now() });
  if (_ring.length > CAPACITY) _ring.splice(0, _ring.length - CAPACITY);
}

export function getSemaphoreContentionTrace(): ReadonlyArray<SemaphoreContentionTraceEntry> {
  return [..._ring];
}

export function clearSemaphoreContentionTrace(): void {
  _ring.length = 0;
}
