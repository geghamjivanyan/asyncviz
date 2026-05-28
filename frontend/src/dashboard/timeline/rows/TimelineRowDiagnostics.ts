/**
 * Row diagnostics facade.
 *
 * Re-exports the trace + metric primitives so the diagnostics page can
 * import a single barrel. Wraps the snapshot in a lightweight derived
 * payload so consumers don't have to know about every counter
 * internally.
 */

import {
  getTimelineRowMetrics,
  type TimelineRowMetrics,
  type TimelineRowMetricsSnapshot,
} from "@/dashboard/timeline/rows/TimelineRowMetrics";
import {
  clearRowTrace,
  getRowTraceSnapshot,
  isRowTraceEnabled,
  recordRowTrace,
  setRowTraceEnabled,
  type RowRendererTraceEntry,
} from "@/dashboard/timeline/rows/diagnostics/rowTrace";

export interface RowDiagnosticsSnapshot {
  metrics: TimelineRowMetricsSnapshot;
  trace: readonly RowRendererTraceEntry[];
  traceEnabled: boolean;
}

export function getRowDiagnosticsSnapshot(
  metrics: TimelineRowMetrics = getTimelineRowMetrics(),
): RowDiagnosticsSnapshot {
  return {
    metrics: metrics.snapshot(),
    trace: getRowTraceSnapshot(),
    traceEnabled: isRowTraceEnabled(),
  };
}

export {
  clearRowTrace,
  getRowTraceSnapshot,
  isRowTraceEnabled,
  recordRowTrace,
  setRowTraceEnabled,
};
export type { RowRendererTraceEntry };
