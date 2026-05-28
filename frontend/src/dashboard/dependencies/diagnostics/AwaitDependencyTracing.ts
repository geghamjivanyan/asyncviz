/**
 * Bounded ring buffer for dependency-graph render diagnostics.
 *
 * Off by default. Diagnostics page exposes a tail of recent entries.
 */

const CAPACITY = 256;

export type AwaitDependencyTraceKind =
  | "ws-payload-applied"
  | "ws-payload-dropped"
  | "panel-rendered"
  | "canvas-rendered"
  | "layout-computed"
  | "selection-changed"
  | "inspector-revealed";

export interface AwaitDependencyTraceEntry {
  kind: AwaitDependencyTraceKind;
  detail: string;
  at: number;
}

let _enabled = false;
const _ring: AwaitDependencyTraceEntry[] = [];

export function isAwaitDependencyTraceEnabled(): boolean { return _enabled; }

export function setAwaitDependencyTraceEnabled(enabled: boolean): void {
  _enabled = enabled;
  if (!enabled) _ring.length = 0;
}

export function recordAwaitDependencyTrace(
  entry: Omit<AwaitDependencyTraceEntry, "at">,
): void {
  if (!_enabled) return;
  _ring.push({ ...entry, at: Date.now() });
  if (_ring.length > CAPACITY) _ring.splice(0, _ring.length - CAPACITY);
}

export function getAwaitDependencyTrace(): ReadonlyArray<AwaitDependencyTraceEntry> {
  return [..._ring];
}

export function clearAwaitDependencyTrace(): void { _ring.length = 0; }
