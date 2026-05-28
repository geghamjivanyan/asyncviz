/**
 * Convenience facade over the scale trace ring buffer.
 */

import {
  clearScaleTrace,
  getScaleTraceSnapshot,
  isScaleTraceEnabled,
  recordScaleTrace,
  setScaleTraceEnabled,
  type ScaleTraceEntry,
  type ScaleTraceKind,
} from "@/dashboard/timeline/scaling/diagnostics/scaleTrace";

export function traceScaleSet(detail: string): void {
  recordScaleTrace({ kind: "scale-set", detail });
}

export function traceZoom(detail: string): void {
  recordScaleTrace({ kind: "zoom", detail });
}

export function tracePan(detail: string): void {
  recordScaleTrace({ kind: "pan", detail });
}

export function traceFit(detail: string): void {
  recordScaleTrace({ kind: "fit", detail });
}

export function traceNormalize(detail: string): void {
  recordScaleTrace({ kind: "normalize", detail });
}

export function traceTickBuild(detail: string): void {
  recordScaleTrace({ kind: "tick-build", detail });
}

export function traceTickCacheHit(detail: string): void {
  recordScaleTrace({ kind: "tick-cache", detail });
}

export function traceConstraintHit(detail: string): void {
  recordScaleTrace({ kind: "constraint-hit", detail });
}

export function tracePrecisionWarning(detail: string): void {
  recordScaleTrace({ kind: "precision-warning", detail });
}

export function traceScaleInvalidate(detail: string): void {
  recordScaleTrace({ kind: "invalidate", detail });
}

export {
  clearScaleTrace,
  getScaleTraceSnapshot,
  isScaleTraceEnabled,
  recordScaleTrace,
  setScaleTraceEnabled,
};
export type { ScaleTraceEntry, ScaleTraceKind };
