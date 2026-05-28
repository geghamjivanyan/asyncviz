/**
 * Convenience facade over the inspector trace ring buffer.
 */

import {
  clearInspectorTrace,
  getInspectorTraceSnapshot,
  isInspectorTraceEnabled,
  recordInspectorTrace,
  setInspectorTraceEnabled,
  type InspectorTraceEntry,
  type InspectorTraceKind,
} from "@/dashboard/inspector/diagnostics/inspectorTrace";

export function traceInspectorProjection(detail: string): void {
  recordInspectorTrace({ kind: "projection", detail });
}

export function traceInspectorPanelRender(detail: string): void {
  recordInspectorTrace({ kind: "panel-render", detail });
}

export function traceInspectorPanelSwitch(detail: string): void {
  recordInspectorTrace({ kind: "panel-switch", detail });
}

export function traceInspectorReveal(detail: string): void {
  recordInspectorTrace({ kind: "reveal", detail });
}

export function traceInspectorFit(detail: string): void {
  recordInspectorTrace({ kind: "fit", detail });
}

export function traceInspectorWarningCorrelation(detail: string): void {
  recordInspectorTrace({ kind: "warning-correlation", detail });
}

export function traceInspectorEmptyState(detail: string): void {
  recordInspectorTrace({ kind: "empty-state", detail });
}

export function traceInspectorLoadingState(detail: string): void {
  recordInspectorTrace({ kind: "loading-state", detail });
}

export {
  clearInspectorTrace,
  getInspectorTraceSnapshot,
  isInspectorTraceEnabled,
  recordInspectorTrace,
  setInspectorTraceEnabled,
};
export type { InspectorTraceEntry, InspectorTraceKind };
