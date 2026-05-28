/**
 * Virtualization diagnostics facade. Combines metrics + trace.
 */

import {
  getTimelineWindowMetrics,
  type TimelineWindowMetrics,
  type TimelineWindowMetricsSnapshot,
} from "@/dashboard/timeline/virtualization/TimelineWindowMetrics";
import {
  clearVirtualizationTrace,
  getVirtualizationTraceSnapshot,
  isVirtualizationTraceEnabled,
  recordVirtualizationTrace,
  setVirtualizationTraceEnabled,
  type VirtualizationTraceEntry,
} from "@/dashboard/timeline/virtualization/diagnostics/virtualizationTrace";

export interface VirtualizationDiagnosticsSnapshot {
  metrics: TimelineWindowMetricsSnapshot;
  trace: readonly VirtualizationTraceEntry[];
  traceEnabled: boolean;
}

export function getVirtualizationDiagnosticsSnapshot(
  metrics: TimelineWindowMetrics = getTimelineWindowMetrics(),
): VirtualizationDiagnosticsSnapshot {
  return {
    metrics: metrics.snapshot(),
    trace: getVirtualizationTraceSnapshot(),
    traceEnabled: isVirtualizationTraceEnabled(),
  };
}

export {
  clearVirtualizationTrace,
  getVirtualizationTraceSnapshot,
  isVirtualizationTraceEnabled,
  recordVirtualizationTrace,
  setVirtualizationTraceEnabled,
};
export type { VirtualizationTraceEntry };
