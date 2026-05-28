/**
 * Diagnostics facade — combines metrics + trace.
 */

import {
  getTimelinePanMetrics,
  type TimelinePanMetrics,
  type TimelinePanMetricsSnapshot,
} from "@/dashboard/timeline/pan/TimelinePanMetrics";
import {
  clearPanTrace,
  getPanTraceSnapshot,
  isPanTraceEnabled,
  recordPanTrace,
  setPanTraceEnabled,
  type PanTraceEntry,
} from "@/dashboard/timeline/pan/diagnostics/panTrace";

export interface PanDiagnosticsSnapshot {
  metrics: TimelinePanMetricsSnapshot;
  trace: readonly PanTraceEntry[];
  traceEnabled: boolean;
}

export function getPanDiagnosticsSnapshot(
  metrics: TimelinePanMetrics = getTimelinePanMetrics(),
): PanDiagnosticsSnapshot {
  return {
    metrics: metrics.snapshot(),
    trace: getPanTraceSnapshot(),
    traceEnabled: isPanTraceEnabled(),
  };
}

export {
  clearPanTrace,
  getPanTraceSnapshot,
  isPanTraceEnabled,
  recordPanTrace,
  setPanTraceEnabled,
};
export type { PanTraceEntry };
