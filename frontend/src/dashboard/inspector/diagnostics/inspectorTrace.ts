/**
 * Ring-buffer tracer for the task inspector. Disabled by default.
 */

const CAPACITY = 256;

export type InspectorTraceKind =
  | "projection"
  | "panel-render"
  | "panel-switch"
  | "reveal"
  | "fit"
  | "warning-correlation"
  | "empty-state"
  | "loading-state";

export interface InspectorTraceEntry {
  kind: InspectorTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: InspectorTraceEntry[] = [];

export function setInspectorTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isInspectorTraceEnabled(): boolean {
  return enabled;
}

export function recordInspectorTrace(entry: Omit<InspectorTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getInspectorTraceSnapshot(): readonly InspectorTraceEntry[] {
  return [...ring];
}

export function clearInspectorTrace(): void {
  ring.length = 0;
}
