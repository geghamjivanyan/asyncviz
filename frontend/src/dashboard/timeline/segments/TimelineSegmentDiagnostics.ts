/**
 * Segment diagnostics facade.
 *
 * Re-exports the trace + metric primitives so the diagnostics page
 * imports a single barrel. Wraps the snapshot in a lightweight
 * derived payload so consumers don't have to know every counter
 * internally.
 */

import {
  getTimelineSegmentMetrics,
  type TimelineSegmentMetrics,
  type TimelineSegmentMetricsSnapshot,
} from "@/dashboard/timeline/segments/TimelineSegmentMetrics";
import {
  clearSegmentTrace,
  getSegmentTraceSnapshot,
  isSegmentTraceEnabled,
  recordSegmentTrace,
  setSegmentTraceEnabled,
  type SegmentTraceEntry,
} from "@/dashboard/timeline/segments/diagnostics/segmentTrace";

export interface SegmentDiagnosticsSnapshot {
  metrics: TimelineSegmentMetricsSnapshot;
  trace: readonly SegmentTraceEntry[];
  traceEnabled: boolean;
}

export function getSegmentDiagnosticsSnapshot(
  metrics: TimelineSegmentMetrics = getTimelineSegmentMetrics(),
): SegmentDiagnosticsSnapshot {
  return {
    metrics: metrics.snapshot(),
    trace: getSegmentTraceSnapshot(),
    traceEnabled: isSegmentTraceEnabled(),
  };
}

export {
  clearSegmentTrace,
  getSegmentTraceSnapshot,
  isSegmentTraceEnabled,
  recordSegmentTrace,
  setSegmentTraceEnabled,
};
export type { SegmentTraceEntry };
