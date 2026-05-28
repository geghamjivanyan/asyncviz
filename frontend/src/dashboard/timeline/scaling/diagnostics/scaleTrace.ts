/**
 * Ring-buffer tracer for the scale engine. Disabled by default.
 */

const CAPACITY = 256;

export type ScaleTraceKind =
  | "scale-set"
  | "zoom"
  | "pan"
  | "fit"
  | "normalize"
  | "tick-build"
  | "tick-cache"
  | "constraint-hit"
  | "precision-warning"
  | "invalidate";

export interface ScaleTraceEntry {
  kind: ScaleTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: ScaleTraceEntry[] = [];

export function setScaleTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isScaleTraceEnabled(): boolean {
  return enabled;
}

export function recordScaleTrace(entry: Omit<ScaleTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getScaleTraceSnapshot(): readonly ScaleTraceEntry[] {
  return [...ring];
}

export function clearScaleTrace(): void {
  ring.length = 0;
}
