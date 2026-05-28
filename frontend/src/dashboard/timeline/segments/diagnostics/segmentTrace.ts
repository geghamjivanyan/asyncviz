/**
 * Lightweight ring-buffer tracer for the segment renderer.
 *
 * Disabled by default. When enabled, every frame + projection rebuild
 * records a structured trace entry. The diagnostics page can surface
 * this without writing to ``console``.
 */

const CAPACITY = 256;

export type SegmentTraceKind =
  | "frame"
  | "projection"
  | "hit"
  | "cull"
  | "overlap"
  | "geometry"
  | "warning"
  | "selection";

export interface SegmentTraceEntry {
  kind: SegmentTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: SegmentTraceEntry[] = [];

export function setSegmentTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isSegmentTraceEnabled(): boolean {
  return enabled;
}

export function recordSegmentTrace(entry: Omit<SegmentTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getSegmentTraceSnapshot(): readonly SegmentTraceEntry[] {
  return [...ring];
}

export function clearSegmentTrace(): void {
  ring.length = 0;
}
