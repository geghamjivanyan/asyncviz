/**
 * Ring-buffer tracer for the virtualization engine. Disabled by
 * default.
 */

const CAPACITY = 256;

export type VirtualizationTraceKind =
  | "window-resolve"
  | "row-cull"
  | "segment-cull"
  | "cache-hit"
  | "cache-miss"
  | "index-build"
  | "invalidate";

export interface VirtualizationTraceEntry {
  kind: VirtualizationTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: VirtualizationTraceEntry[] = [];

export function setVirtualizationTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isVirtualizationTraceEnabled(): boolean {
  return enabled;
}

export function recordVirtualizationTrace(entry: Omit<VirtualizationTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getVirtualizationTraceSnapshot(): readonly VirtualizationTraceEntry[] {
  return [...ring];
}

export function clearVirtualizationTrace(): void {
  ring.length = 0;
}
