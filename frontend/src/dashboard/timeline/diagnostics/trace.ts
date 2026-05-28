/**
 * Lightweight ring-buffer tracer for the timeline renderer.
 *
 * Disabled by default. When enabled, every render frame + every
 * invalidation records a structured trace. The diagnostics page can
 * surface this without writing to ``console``.
 */

const CAPACITY = 256;

export interface RendererTraceEntry {
  kind: "frame" | "invalidation" | "resize" | "selection" | "hover";
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: RendererTraceEntry[] = [];

export function setRendererTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isRendererTraceEnabled(): boolean {
  return enabled;
}

export function recordRendererTrace(entry: Omit<RendererTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getRendererTraceSnapshot(): readonly RendererTraceEntry[] {
  return [...ring];
}

export function clearRendererTrace(): void {
  ring.length = 0;
}
