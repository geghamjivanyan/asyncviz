/**
 * Ring-buffer tracer for the zoom controller. Disabled by default.
 */

const CAPACITY = 256;

export type ZoomTraceKind =
  | "zoom-in"
  | "zoom-out"
  | "zoom-fit"
  | "zoom-set-level"
  | "zoom-by-factor"
  | "preset"
  | "shortcut"
  | "wheel"
  | "pinch"
  | "noop";

export interface ZoomTraceEntry {
  kind: ZoomTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: ZoomTraceEntry[] = [];

export function setZoomTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isZoomTraceEnabled(): boolean {
  return enabled;
}

export function recordZoomTrace(entry: Omit<ZoomTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getZoomTraceSnapshot(): readonly ZoomTraceEntry[] {
  return [...ring];
}

export function clearZoomTrace(): void {
  ring.length = 0;
}
