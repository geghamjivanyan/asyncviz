/**
 * Diagnostics facade — combines metrics + trace into one snapshot.
 */

import {
  getTimelineZoomMetrics,
  type TimelineZoomMetrics,
  type TimelineZoomMetricsSnapshot,
} from "@/dashboard/timeline/zoom/TimelineZoomMetrics";
import {
  clearZoomTrace,
  getZoomTraceSnapshot,
  isZoomTraceEnabled,
  recordZoomTrace,
  setZoomTraceEnabled,
  type ZoomTraceEntry,
} from "@/dashboard/timeline/zoom/diagnostics/zoomTrace";

export interface ZoomDiagnosticsSnapshot {
  metrics: TimelineZoomMetricsSnapshot;
  trace: readonly ZoomTraceEntry[];
  traceEnabled: boolean;
}

export function getZoomDiagnosticsSnapshot(
  metrics: TimelineZoomMetrics = getTimelineZoomMetrics(),
): ZoomDiagnosticsSnapshot {
  return {
    metrics: metrics.snapshot(),
    trace: getZoomTraceSnapshot(),
    traceEnabled: isZoomTraceEnabled(),
  };
}

export {
  clearZoomTrace,
  getZoomTraceSnapshot,
  isZoomTraceEnabled,
  recordZoomTrace,
  setZoomTraceEnabled,
};
export type { ZoomTraceEntry };
