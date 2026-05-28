/**
 * Build a snapshot of replay-timeline state suitable for the
 * diagnostics page (frontend-side counterpart of the backend's
 * :class:`ReplayLoaderDiagnostics`).
 */

import {
  getReplayTimelineMetricsSnapshot,
  type ReplayTimelineMetricsSnapshot,
} from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import {
  getReplayTimelineTrace,
  isReplayTimelineTraceEnabled,
  type ReplayTimelineTraceEntry,
} from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";
import type { ReplayTimelineStats } from "@/dashboard/replay/ReplayTimelineStore";

export interface ReplayTimelineDiagnostics {
  readonly stats: ReplayTimelineStats;
  readonly metrics: ReplayTimelineMetricsSnapshot;
  readonly traceEnabled: boolean;
  readonly recentTrace: readonly ReplayTimelineTraceEntry[];
}

export function buildReplayTimelineDiagnostics(
  stats: ReplayTimelineStats,
  traceLimit: number = 32,
): ReplayTimelineDiagnostics {
  const fullTrace = getReplayTimelineTrace();
  return {
    stats,
    metrics: getReplayTimelineMetricsSnapshot(),
    traceEnabled: isReplayTimelineTraceEnabled(),
    recentTrace:
      traceLimit > 0 ? fullTrace.slice(-traceLimit) : fullTrace,
  };
}
