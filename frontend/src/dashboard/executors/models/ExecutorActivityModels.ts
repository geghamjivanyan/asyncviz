/**
 * Wire + view models for the executor activity visualization layer.
 *
 * Mirrors the backend types in
 * :mod:`asyncviz.instrumentation.executor.metrics.executor_metrics_models`
 * and the diagnostics shape returned by ``GET /api/executor/metrics``.
 * Kept dependency-free so the projection / renderer / store layers
 * can import without React.
 */

// ── shared ──────────────────────────────────────────────────────────────

export type ExecutorKind =
  | "Thread"
  | "Process"
  | "default"
  | "custom"
  | "unknown";

/** Backend saturation level. */
export type ExecutorSaturationLevel = "calm" | "warning" | "critical";

/** Visual severity bucket — cards + markers key colors off this.
 *  Saturated outranks the score-based critical because zero permits +
 *  parked waiters is the most actionable signal for operators. */
export type ExecutorActivitySeverity =
  | "calm"
  | "warning"
  | "critical"
  | "saturated";

// ── wire-shape: per-executor sub-records ────────────────────────────────

export interface ExecutorUtilizationRecord {
  active_workers: number;
  peak_active_workers: number;
  max_workers: number | null;
  utilization_ratio: number;
  mean_utilization: number;
  sample_count: number;
}

export interface ExecutorThroughputRecord {
  submissions: number;
  completions: number;
  failures: number;
  cancellations: number;
  submission_rate: number;
  completion_rate: number;
  backlog: number;
}

export interface ExecutorLatencyRecord {
  count: number;
  mean_seconds: number;
  p50_seconds: number;
  p95_seconds: number;
  p99_seconds: number;
  max_seconds: number;
}

export interface ExecutorSaturationRecord {
  saturation_score: number;
  level: ExecutorSaturationLevel;
  peak_utilization_ratio: number;
  backlog_velocity: number;
}

export interface ExecutorMetricsRecord {
  executor_id: string;
  executor_kind: ExecutorKind;
  max_workers: number | null;
  sequence: number;
  utilization: ExecutorUtilizationRecord;
  throughput: ExecutorThroughputRecord;
  saturation: ExecutorSaturationRecord;
  submission_latency: ExecutorLatencyRecord;
  execution_duration: ExecutorLatencyRecord;
}

// ── wire-shape: engine self-metrics + hydration ─────────────────────────

export interface ExecutorEngineSelfRecord {
  events_observed: number;
  events_ignored: number;
  events_dropped: number;
  updates_emitted: number;
  saturation_transitions: number;
  contention_detections: number;
  latency_spike_detections: number;
  tracked_executors: number;
  executors_evicted: number;
  recursion_skips: number;
}

export interface ExecutorActivityHydrationResponse {
  executors: ExecutorMetricsRecord[];
  self_metrics: ExecutorEngineSelfRecord;
  config: Record<string, unknown>;
  trace_enabled: boolean;
  trace_count: number;
  recent_trace: ReadonlyArray<{
    kind: string;
    detail: string;
    at_monotonic: number;
  }>;
}

// ── wire-shape: engine-emitted aggregate events ─────────────────────────

interface _ExecutorEventBase {
  event_type: string;
  executor_id: string;
  executor_kind: ExecutorKind;
  max_workers: number | null;
  sequence: number;
  snapshot: Record<string, unknown>;
}

export interface ExecutorMetricsUpdatedPayload extends _ExecutorEventBase {
  event_type: "asyncio.executor.metrics.updated";
  active_workers: number;
  peak_active_workers: number;
  utilization_ratio: number;
  mean_utilization: number;
  submissions: number;
  completions: number;
  failures: number;
  cancellations: number;
  submission_rate: number;
  completion_rate: number;
  backlog: number;
  mean_submission_latency_seconds: number;
  p95_submission_latency_seconds: number;
  mean_execution_duration_seconds: number;
  p95_execution_duration_seconds: number;
  saturation_score: number;
  saturation_level: ExecutorSaturationLevel;
}

export interface ExecutorSaturationChangedPayload extends _ExecutorEventBase {
  event_type: "asyncio.executor.saturation.changed";
  previous_level: ExecutorSaturationLevel;
  new_level: ExecutorSaturationLevel;
  saturation_score: number;
  utilization_ratio: number;
  backlog: number;
}

export interface ExecutorContentionDetectedPayload extends _ExecutorEventBase {
  event_type: "asyncio.executor.contention.detected";
  active_workers: number;
  utilization_ratio: number;
}

export interface ExecutorLatencySpikeDetectedPayload extends _ExecutorEventBase {
  event_type: "asyncio.executor.latency.spike.detected";
  submission_latency_seconds: number;
  threshold_seconds: number;
  active_workers: number;
}

export type ExecutorActivityEventPayload =
  | ExecutorMetricsUpdatedPayload
  | ExecutorSaturationChangedPayload
  | ExecutorContentionDetectedPayload
  | ExecutorLatencySpikeDetectedPayload;

export const EXECUTOR_METRICS_EVENT_TYPES = [
  "asyncio.executor.metrics.updated",
  "asyncio.executor.saturation.changed",
  "asyncio.executor.contention.detected",
  "asyncio.executor.latency.spike.detected",
] as const;

export type ExecutorActivityEventType =
  (typeof EXECUTOR_METRICS_EVENT_TYPES)[number];

// ── view-shape (projection-layer output) ────────────────────────────────

export interface ExecutorActivityView {
  executorId: string;
  executorKind: ExecutorKind;
  displayName: string;
  maxWorkers: number | null;
  activeWorkers: number;
  peakActiveWorkers: number;
  utilizationRatio: number;
  meanUtilization: number;
  submissions: number;
  completions: number;
  failures: number;
  cancellations: number;
  submissionRate: number;
  completionRate: number;
  backlog: number;
  meanSubmissionLatencySeconds: number;
  p95SubmissionLatencySeconds: number;
  meanExecutionDurationSeconds: number;
  p95ExecutionDurationSeconds: number;
  saturationScore: number;
  saturationLevel: ExecutorSaturationLevel;
  saturated: boolean;
  severity: ExecutorActivitySeverity;
  sequence: number;
}

// ── timeline marker view-shape ──────────────────────────────────────────

export type ExecutorMarkerKind =
  | "saturation-changed"
  | "contention"
  | "latency-spike";

export interface ExecutorActivityMarker {
  id: string;
  executorId: string;
  kind: ExecutorMarkerKind;
  severity: ExecutorActivitySeverity;
  monotonicNs: number;
  label: string;
  detail?: string;
}
