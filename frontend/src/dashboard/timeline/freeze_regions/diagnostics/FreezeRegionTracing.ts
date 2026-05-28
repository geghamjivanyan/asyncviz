/**
 * Ring-buffer tracer for the freeze-region layer.
 *
 * Disabled by default; the diagnostics page toggles it on for live
 * inspection. Same pattern as the other tracers in the codebase.
 */

const CAPACITY = 256;

export type FreezeRegionTraceKind =
  | "layer-attached"
  | "layer-detached"
  | "frame"
  | "selection-changed"
  | "hover-changed"
  | "reveal"
  | "reveal-missed";

export interface FreezeRegionTraceEntry {
  kind: FreezeRegionTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: FreezeRegionTraceEntry[] = [];

export function setFreezeRegionTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isFreezeRegionTraceEnabled(): boolean {
  return enabled;
}

export function recordFreezeRegionTrace(
  entry: Omit<FreezeRegionTraceEntry, "atMs">,
): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getFreezeRegionTraceSnapshot(): readonly FreezeRegionTraceEntry[] {
  return [...ring];
}

export function clearFreezeRegionTrace(): void {
  ring.length = 0;
}
