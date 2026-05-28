/**
 * Ring-buffer tracer for the pan controller. Disabled by default.
 */

const CAPACITY = 256;

export type PanTraceKind =
  | "pan"
  | "drag-start"
  | "drag-update"
  | "drag-end"
  | "drag-cancel"
  | "wheel"
  | "keyboard"
  | "center"
  | "to-time"
  | "constraint-hit"
  | "noop";

export interface PanTraceEntry {
  kind: PanTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: PanTraceEntry[] = [];

export function setPanTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isPanTraceEnabled(): boolean {
  return enabled;
}

export function recordPanTrace(entry: Omit<PanTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getPanTraceSnapshot(): readonly PanTraceEntry[] {
  return [...ring];
}

export function clearPanTrace(): void {
  ring.length = 0;
}
