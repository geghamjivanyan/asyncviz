/**
 * Ring-buffer tracer for the live update engine. Disabled by default.
 */

const CAPACITY = 256;

export type LiveTraceKind =
  | "envelope"
  | "invalidate"
  | "flush"
  | "replay"
  | "active-tick"
  | "mode-change"
  | "frame-request";

export interface LiveTraceEntry {
  kind: LiveTraceKind;
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: LiveTraceEntry[] = [];

export function setLiveTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isLiveTraceEnabled(): boolean {
  return enabled;
}

export function recordLiveTrace(entry: Omit<LiveTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getLiveTraceSnapshot(): readonly LiveTraceEntry[] {
  return [...ring];
}

export function clearLiveTrace(): void {
  ring.length = 0;
}
