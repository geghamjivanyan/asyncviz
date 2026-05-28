/**
 * Diagnostics facade — combines metrics + trace.
 */

import {
  getTimelineSelectionMetrics,
  type TimelineSelectionMetrics,
  type TimelineSelectionMetricsSnapshot,
} from "@/dashboard/timeline/selection/TimelineSelectionMetrics";
import {
  clearSelectionTrace,
  getSelectionTraceSnapshot,
  isSelectionTraceEnabled,
  recordSelectionTrace,
  setSelectionTraceEnabled,
  type SelectionTraceEntry,
} from "@/dashboard/timeline/selection/diagnostics/selectionTrace";

export interface SelectionDiagnosticsSnapshot {
  metrics: TimelineSelectionMetricsSnapshot;
  trace: readonly SelectionTraceEntry[];
  traceEnabled: boolean;
}

export function getSelectionDiagnosticsSnapshot(
  metrics: TimelineSelectionMetrics = getTimelineSelectionMetrics(),
): SelectionDiagnosticsSnapshot {
  return {
    metrics: metrics.snapshot(),
    trace: getSelectionTraceSnapshot(),
    traceEnabled: isSelectionTraceEnabled(),
  };
}

export {
  clearSelectionTrace,
  getSelectionTraceSnapshot,
  isSelectionTraceEnabled,
  recordSelectionTrace,
  setSelectionTraceEnabled,
};
export type { SelectionTraceEntry };
