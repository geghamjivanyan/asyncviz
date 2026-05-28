/**
 * Convenience facade over the selection trace ring buffer.
 */

import {
  clearSelectionTrace,
  getSelectionTraceSnapshot,
  isSelectionTraceEnabled,
  recordSelectionTrace,
  setSelectionTraceEnabled,
  type SelectionTraceEntry,
  type SelectionTraceKind,
} from "@/dashboard/timeline/selection/diagnostics/selectionTrace";

export function traceSelectionSelect(detail: string): void {
  recordSelectionTrace({ kind: "select", detail });
}

export function traceSelectionClear(detail: string): void {
  recordSelectionTrace({ kind: "clear", detail });
}

export function traceSelectionNavigate(detail: string): void {
  recordSelectionTrace({ kind: "navigate", detail });
}

export function traceSelectionCenter(detail: string): void {
  recordSelectionTrace({ kind: "center", detail });
}

export function traceSelectionReveal(detail: string): void {
  recordSelectionTrace({ kind: "reveal", detail });
}

export function traceSelectionRestore(detail: string): void {
  recordSelectionTrace({ kind: "restore", detail });
}

export function traceSelectionNoop(detail: string): void {
  recordSelectionTrace({ kind: "noop", detail });
}

export {
  clearSelectionTrace,
  getSelectionTraceSnapshot,
  isSelectionTraceEnabled,
  recordSelectionTrace,
  setSelectionTraceEnabled,
};
export type { SelectionTraceEntry, SelectionTraceKind };
