/**
 * Ring-buffer tracer for the blocking-warning panel.
 *
 * Disabled by default — call :func:`setBlockingWarningTraceEnabled`
 * from the diagnostics panel to flip the flag. Same pattern as the
 * inspector + state-store tracers so DevTools can read all three rings
 * uniformly.
 */

const CAPACITY = 256;

export type BlockingWarningTraceKind =
  | "snapshot-fetched"
  | "snapshot-failed"
  | "store-hydrated"
  | "event-applied"
  | "event-dropped"
  | "filter-changed"
  | "selection-changed"
  | "reveal-task"
  | "reveal-capture"
  | "panel-render"
  | "panel-empty";

export interface BlockingWarningTraceEntry {
  kind: BlockingWarningTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: BlockingWarningTraceEntry[] = [];

export function setBlockingWarningTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isBlockingWarningTraceEnabled(): boolean {
  return enabled;
}

export function recordBlockingWarningTrace(entry: Omit<BlockingWarningTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getBlockingWarningTraceSnapshot(): readonly BlockingWarningTraceEntry[] {
  return [...ring];
}

export function clearBlockingWarningTrace(): void {
  ring.length = 0;
}
