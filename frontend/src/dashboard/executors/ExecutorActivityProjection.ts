/**
 * Pure projection: ``ExecutorMetricsRecord`` → ``ExecutorActivityView``.
 *
 * Same pattern as the queue + semaphore projection layers.
 */

import type {
  ExecutorActivityMarker,
  ExecutorActivityView,
  ExecutorMetricsRecord,
} from "@/dashboard/executors/models/ExecutorActivityModels";
import {
  compareSeverityDesc,
  deriveSeverity,
  markerLabel,
} from "@/dashboard/executors/ExecutorActivitySeverity";

export interface ExecutorActivityProjectionInputs {
  records: ReadonlyArray<ExecutorMetricsRecord>;
  /** Optional per-executor name overrides; defaults to the executor id. */
  displayNames?: Readonly<Record<string, string>>;
}

export interface ExecutorActivityProjection {
  views: ExecutorActivityView[];
  bySeverityDescending: ExecutorActivityView[];
  /** Number of executors with severity ≥ ``warning``. */
  alarmCount: number;
}

export function projectExecutorActivity(
  inputs: ExecutorActivityProjectionInputs,
): ExecutorActivityProjection {
  const views = inputs.records.map((record) =>
    projectRecord(record, inputs.displayNames?.[record.executor_id]),
  );
  const bySeverityDescending = [...views].sort((a, b) => {
    const sev = compareSeverityDesc(a.severity, b.severity);
    if (sev !== 0) return sev;
    if (a.saturationScore !== b.saturationScore) {
      return b.saturationScore - a.saturationScore;
    }
    return a.displayName.localeCompare(b.displayName);
  });
  let alarmCount = 0;
  for (const view of views) {
    if (view.severity !== "calm") alarmCount += 1;
  }
  return { views, bySeverityDescending, alarmCount };
}

export function projectRecord(
  record: ExecutorMetricsRecord,
  displayName?: string,
): ExecutorActivityView {
  const severity = deriveSeverity({
    level: record.saturation.level,
    utilizationRatio: record.utilization.utilization_ratio,
    backlog: record.throughput.backlog,
  });
  return {
    executorId: record.executor_id,
    executorKind: record.executor_kind,
    displayName: displayName ?? record.executor_id,
    maxWorkers: record.max_workers,
    activeWorkers: record.utilization.active_workers,
    peakActiveWorkers: record.utilization.peak_active_workers,
    utilizationRatio: record.utilization.utilization_ratio,
    meanUtilization: record.utilization.mean_utilization,
    submissions: record.throughput.submissions,
    completions: record.throughput.completions,
    failures: record.throughput.failures,
    cancellations: record.throughput.cancellations,
    submissionRate: record.throughput.submission_rate,
    completionRate: record.throughput.completion_rate,
    backlog: record.throughput.backlog,
    meanSubmissionLatencySeconds: record.submission_latency.mean_seconds,
    p95SubmissionLatencySeconds: record.submission_latency.p95_seconds,
    meanExecutionDurationSeconds: record.execution_duration.mean_seconds,
    p95ExecutionDurationSeconds: record.execution_duration.p95_seconds,
    saturationScore: record.saturation.saturation_score,
    saturationLevel: record.saturation.level,
    saturated: severity === "saturated",
    severity,
    sequence: record.sequence,
  };
}

// ── marker projection ───────────────────────────────────────────────────

export interface MarkerProjectionInputs {
  markers: ReadonlyArray<ExecutorActivityMarker>;
  startNs?: number;
  endNs?: number;
  limit?: number;
}

export function projectMarkersInWindow(
  inputs: MarkerProjectionInputs,
): ExecutorActivityMarker[] {
  const { markers, startNs, endNs, limit } = inputs;
  if (markers.length === 0) return [];
  const out: ExecutorActivityMarker[] = [];
  for (const marker of markers) {
    if (startNs !== undefined && marker.monotonicNs < startNs) continue;
    if (endNs !== undefined && marker.monotonicNs > endNs) continue;
    out.push(marker);
    if (limit !== undefined && out.length >= limit) break;
  }
  return out;
}

export function describeMarker(marker: ExecutorActivityMarker): string {
  const head = markerLabel(marker.kind);
  return marker.detail ? `${head}: ${marker.detail}` : head;
}
