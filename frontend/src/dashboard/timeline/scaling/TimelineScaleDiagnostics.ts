/**
 * Diagnostics facade — combines metrics + trace.
 */

import {
  getTimelineScaleMetrics,
  type TimelineScaleMetrics,
  type TimelineScaleMetricsSnapshot,
} from "@/dashboard/timeline/scaling/TimelineScaleMetrics";
import {
  clearScaleTrace,
  getScaleTraceSnapshot,
  isScaleTraceEnabled,
  recordScaleTrace,
  setScaleTraceEnabled,
  type ScaleTraceEntry,
} from "@/dashboard/timeline/scaling/diagnostics/scaleTrace";

export interface ScaleDiagnosticsSnapshot {
  metrics: TimelineScaleMetricsSnapshot;
  trace: readonly ScaleTraceEntry[];
  traceEnabled: boolean;
}

export function getScaleDiagnosticsSnapshot(
  metrics: TimelineScaleMetrics = getTimelineScaleMetrics(),
): ScaleDiagnosticsSnapshot {
  return {
    metrics: metrics.snapshot(),
    trace: getScaleTraceSnapshot(),
    traceEnabled: isScaleTraceEnabled(),
  };
}

export {
  clearScaleTrace,
  getScaleTraceSnapshot,
  isScaleTraceEnabled,
  recordScaleTrace,
  setScaleTraceEnabled,
};
export type { ScaleTraceEntry };
