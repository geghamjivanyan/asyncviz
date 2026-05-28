/**
 * Convenience facade over the virtualization trace ring buffer.
 */

import {
  clearVirtualizationTrace,
  getVirtualizationTraceSnapshot,
  isVirtualizationTraceEnabled,
  recordVirtualizationTrace,
  setVirtualizationTraceEnabled,
  type VirtualizationTraceEntry,
  type VirtualizationTraceKind,
} from "@/dashboard/timeline/virtualization/diagnostics/virtualizationTrace";

export function traceWindowResolve(detail: string): void {
  recordVirtualizationTrace({ kind: "window-resolve", detail });
}

export function traceRowCull(detail: string): void {
  recordVirtualizationTrace({ kind: "row-cull", detail });
}

export function traceSegmentCull(detail: string): void {
  recordVirtualizationTrace({ kind: "segment-cull", detail });
}

export function traceCacheHit(detail: string): void {
  recordVirtualizationTrace({ kind: "cache-hit", detail });
}

export function traceCacheMiss(detail: string): void {
  recordVirtualizationTrace({ kind: "cache-miss", detail });
}

export function traceIndexBuild(detail: string): void {
  recordVirtualizationTrace({ kind: "index-build", detail });
}

export function traceVirtualizationInvalidate(detail: string): void {
  recordVirtualizationTrace({ kind: "invalidate", detail });
}

export {
  clearVirtualizationTrace,
  getVirtualizationTraceSnapshot,
  isVirtualizationTraceEnabled,
  recordVirtualizationTrace,
  setVirtualizationTraceEnabled,
};
export type { VirtualizationTraceEntry, VirtualizationTraceKind };
