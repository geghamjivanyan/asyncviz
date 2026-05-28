/**
 * Lightweight ring-buffer tracer for the row renderer.
 *
 * Disabled by default. When enabled, every frame + every projection
 * rebuild records a structured trace entry. The diagnostics page can
 * surface this without writing to ``console``.
 */

const CAPACITY = 256;

export interface RowRendererTraceEntry {
  kind: "frame" | "projection" | "hover" | "selection" | "warning" | "layout";
  detail: string;
  atMs: number;
}

let enabled = false;
const ring: RowRendererTraceEntry[] = [];

export function setRowTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring.length = 0;
}

export function isRowTraceEnabled(): boolean {
  return enabled;
}

export function recordRowTrace(entry: Omit<RowRendererTraceEntry, "atMs">): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ ...entry, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getRowTraceSnapshot(): readonly RowRendererTraceEntry[] {
  return [...ring];
}

export function clearRowTrace(): void {
  ring.length = 0;
}
