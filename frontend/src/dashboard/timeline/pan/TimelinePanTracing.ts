/**
 * Convenience facade over the pan trace ring buffer.
 */

import {
  clearPanTrace,
  getPanTraceSnapshot,
  isPanTraceEnabled,
  recordPanTrace,
  setPanTraceEnabled,
  type PanTraceEntry,
  type PanTraceKind,
} from "@/dashboard/timeline/pan/diagnostics/panTrace";

export function tracePan(detail: string): void {
  recordPanTrace({ kind: "pan", detail });
}

export function tracePanDragStart(detail: string): void {
  recordPanTrace({ kind: "drag-start", detail });
}

export function tracePanDragUpdate(detail: string): void {
  recordPanTrace({ kind: "drag-update", detail });
}

export function tracePanDragEnd(detail: string): void {
  recordPanTrace({ kind: "drag-end", detail });
}

export function tracePanDragCancel(detail: string): void {
  recordPanTrace({ kind: "drag-cancel", detail });
}

export function tracePanWheel(detail: string): void {
  recordPanTrace({ kind: "wheel", detail });
}

export function tracePanKeyboard(detail: string): void {
  recordPanTrace({ kind: "keyboard", detail });
}

export function tracePanCenter(detail: string): void {
  recordPanTrace({ kind: "center", detail });
}

export function tracePanToTime(detail: string): void {
  recordPanTrace({ kind: "to-time", detail });
}

export function tracePanConstraintHit(detail: string): void {
  recordPanTrace({ kind: "constraint-hit", detail });
}

export function tracePanNoop(detail: string): void {
  recordPanTrace({ kind: "noop", detail });
}

export {
  clearPanTrace,
  getPanTraceSnapshot,
  isPanTraceEnabled,
  recordPanTrace,
  setPanTraceEnabled,
};
export type { PanTraceEntry, PanTraceKind };
