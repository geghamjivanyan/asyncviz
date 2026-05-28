/**
 * Live diagnostics facade.
 *
 * Combines :class:`TimelineLiveMetrics` + the live trace ring buffer
 * into one snapshot consumers can fetch on a poll.
 */

import {
  getTimelineLiveMetrics,
  type TimelineLiveMetrics,
  type TimelineLiveMetricsSnapshot,
} from "@/dashboard/timeline/live/TimelineLiveMetrics";
import {
  clearLiveTrace,
  getLiveTraceSnapshot,
  isLiveTraceEnabled,
  recordLiveTrace,
  setLiveTraceEnabled,
  type LiveTraceEntry,
} from "@/dashboard/timeline/live/diagnostics/liveTrace";

export interface LiveDiagnosticsSnapshot {
  metrics: TimelineLiveMetricsSnapshot;
  trace: readonly LiveTraceEntry[];
  traceEnabled: boolean;
}

export function getLiveDiagnosticsSnapshot(
  metrics: TimelineLiveMetrics = getTimelineLiveMetrics(),
): LiveDiagnosticsSnapshot {
  return {
    metrics: metrics.snapshot(),
    trace: getLiveTraceSnapshot(),
    traceEnabled: isLiveTraceEnabled(),
  };
}

export {
  clearLiveTrace,
  getLiveTraceSnapshot,
  isLiveTraceEnabled,
  recordLiveTrace,
  setLiveTraceEnabled,
};
export type { LiveTraceEntry };
