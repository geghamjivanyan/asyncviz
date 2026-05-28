/**
 * Ring-buffer tracer for the render-optimization layer.
 *
 * Disabled by default. When enabled, records every frame, pass,
 * cache touch, dirty-region collapse + degradation transition. The
 * diagnostics view surfaces the ring without writing to ``console``.
 */

const CAPACITY = 256;

export type RenderOptimizationTraceKind =
  | "frame"
  | "pass"
  | "dirty-region"
  | "dirty-collapse"
  | "cache-hit"
  | "cache-miss"
  | "degrade"
  | "restore"
  | "overlay-flush"
  | "cursor"
  | "integrity-violation"
  | "diagnostic";

export interface RenderOptimizationTraceEntry {
  readonly kind: RenderOptimizationTraceKind;
  readonly detail: string;
  readonly atMs: number;
}

let enabled = false;
let ring: RenderOptimizationTraceEntry[] = [];

export function setRenderOptimizationTraceEnabled(value: boolean): void {
  enabled = value;
  if (!value) ring = [];
}

export function isRenderOptimizationTraceEnabled(): boolean {
  return enabled;
}

export function recordRenderOptimizationTrace(
  kind: RenderOptimizationTraceKind,
  detail: string,
): void {
  if (!enabled) return;
  const atMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  ring.push({ kind, detail, atMs });
  while (ring.length > CAPACITY) ring.shift();
}

export function getRenderOptimizationTrace(): readonly RenderOptimizationTraceEntry[] {
  return ring.slice();
}

export function clearRenderOptimizationTrace(): void {
  ring = [];
}

export const RENDER_OPT_TRACE_CAPACITY = CAPACITY;
