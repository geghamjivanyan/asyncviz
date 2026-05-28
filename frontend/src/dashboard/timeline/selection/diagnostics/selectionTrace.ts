/**
 * Ring-buffer tracer for the selection controller. Disabled by default.
 */

const CAPACITY = 256;

export type SelectionTraceKind =
  | "select"
  | "clear"
  | "navigate"
  | "center"
  | "reveal"
  | "restore"
  | "noop";

export interface SelectionTraceEntry {
  kind: SelectionTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: SelectionTraceEntry[] = [];

export function setSelectionTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isSelectionTraceEnabled(): boolean {
  return enabled;
}

export function recordSelectionTrace(entry: Omit<SelectionTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getSelectionTraceSnapshot(): readonly SelectionTraceEntry[] {
  return [...ring];
}

export function clearSelectionTrace(): void {
  ring.length = 0;
}
