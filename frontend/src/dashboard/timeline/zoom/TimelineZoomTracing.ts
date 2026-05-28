/**
 * Convenience facade over the zoom trace ring buffer.
 */

import {
  clearZoomTrace,
  getZoomTraceSnapshot,
  isZoomTraceEnabled,
  recordZoomTrace,
  setZoomTraceEnabled,
  type ZoomTraceEntry,
  type ZoomTraceKind,
} from "@/dashboard/timeline/zoom/diagnostics/zoomTrace";

export function traceZoomIn(detail: string): void {
  recordZoomTrace({ kind: "zoom-in", detail });
}

export function traceZoomOut(detail: string): void {
  recordZoomTrace({ kind: "zoom-out", detail });
}

export function traceZoomFit(detail: string): void {
  recordZoomTrace({ kind: "zoom-fit", detail });
}

export function traceZoomSetLevel(detail: string): void {
  recordZoomTrace({ kind: "zoom-set-level", detail });
}

export function traceZoomByFactor(detail: string): void {
  recordZoomTrace({ kind: "zoom-by-factor", detail });
}

export function traceZoomPreset(detail: string): void {
  recordZoomTrace({ kind: "preset", detail });
}

export function traceZoomShortcut(detail: string): void {
  recordZoomTrace({ kind: "shortcut", detail });
}

export function traceZoomWheel(detail: string): void {
  recordZoomTrace({ kind: "wheel", detail });
}

export function traceZoomPinch(detail: string): void {
  recordZoomTrace({ kind: "pinch", detail });
}

export function traceZoomNoop(detail: string): void {
  recordZoomTrace({ kind: "noop", detail });
}

export {
  clearZoomTrace,
  getZoomTraceSnapshot,
  isZoomTraceEnabled,
  recordZoomTrace,
  setZoomTraceEnabled,
};
export type { ZoomTraceEntry, ZoomTraceKind };
