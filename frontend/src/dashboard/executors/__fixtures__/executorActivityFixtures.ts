import type {
  ExecutorActivityEventPayload,
  ExecutorActivityHydrationResponse,
  ExecutorContentionDetectedPayload,
  ExecutorEngineSelfRecord,
  ExecutorLatencyRecord,
  ExecutorLatencySpikeDetectedPayload,
  ExecutorMetricsRecord,
  ExecutorMetricsUpdatedPayload,
  ExecutorSaturationChangedPayload,
} from "@/dashboard/executors/models/ExecutorActivityModels";

function makeLatency(overrides: Partial<ExecutorLatencyRecord> = {}): ExecutorLatencyRecord {
  return {
    count: 0,
    mean_seconds: 0,
    p50_seconds: 0,
    p95_seconds: 0,
    p99_seconds: 0,
    max_seconds: 0,
    ...overrides,
  };
}

export function makeRecord(overrides: Partial<ExecutorMetricsRecord> = {}): ExecutorMetricsRecord {
  return {
    executor_id: "e-1",
    executor_kind: "Thread",
    max_workers: 4,
    sequence: 1,
    utilization: {
      active_workers: 0,
      peak_active_workers: 0,
      max_workers: 4,
      utilization_ratio: 0,
      mean_utilization: 0,
      sample_count: 0,
    },
    throughput: {
      submissions: 0,
      completions: 0,
      failures: 0,
      cancellations: 0,
      submission_rate: 0,
      completion_rate: 0,
      backlog: 0,
    },
    saturation: {
      saturation_score: 0,
      level: "calm",
      peak_utilization_ratio: 0,
      backlog_velocity: 0,
    },
    submission_latency: makeLatency(),
    execution_duration: makeLatency(),
    ...overrides,
  };
}

export function makeSelfMetrics(
  overrides: Partial<ExecutorEngineSelfRecord> = {},
): ExecutorEngineSelfRecord {
  return {
    events_observed: 0,
    events_ignored: 0,
    events_dropped: 0,
    updates_emitted: 0,
    saturation_transitions: 0,
    contention_detections: 0,
    latency_spike_detections: 0,
    tracked_executors: 0,
    executors_evicted: 0,
    recursion_skips: 0,
    ...overrides,
  };
}

export function makeHydration(
  overrides: Partial<ExecutorActivityHydrationResponse> = {},
): ExecutorActivityHydrationResponse {
  return {
    executors: [],
    self_metrics: makeSelfMetrics(),
    config: {},
    trace_enabled: false,
    trace_count: 0,
    recent_trace: [],
    ...overrides,
  };
}

export function makeUpdated(
  overrides: Partial<ExecutorMetricsUpdatedPayload> = {},
): ExecutorMetricsUpdatedPayload & {
  event_type: "asyncio.executor.metrics.updated";
} {
  return {
    event_type: "asyncio.executor.metrics.updated",
    executor_id: "e-1",
    executor_kind: "Thread",
    max_workers: 4,
    sequence: 1,
    snapshot: {},
    active_workers: 0,
    peak_active_workers: 0,
    utilization_ratio: 0,
    mean_utilization: 0,
    submissions: 0,
    completions: 0,
    failures: 0,
    cancellations: 0,
    submission_rate: 0,
    completion_rate: 0,
    backlog: 0,
    mean_submission_latency_seconds: 0,
    p95_submission_latency_seconds: 0,
    mean_execution_duration_seconds: 0,
    p95_execution_duration_seconds: 0,
    saturation_score: 0,
    saturation_level: "calm",
    ...overrides,
  };
}

export function makeSaturationChanged(
  overrides: Partial<ExecutorSaturationChangedPayload> = {},
): ExecutorSaturationChangedPayload & {
  event_type: "asyncio.executor.saturation.changed";
} {
  return {
    event_type: "asyncio.executor.saturation.changed",
    executor_id: "e-1",
    executor_kind: "Thread",
    max_workers: 4,
    sequence: 2,
    snapshot: {},
    previous_level: "calm",
    new_level: "warning",
    saturation_score: 0.72,
    utilization_ratio: 0.8,
    backlog: 4,
    ...overrides,
  };
}

export function makeContention(
  overrides: Partial<ExecutorContentionDetectedPayload> = {},
): ExecutorContentionDetectedPayload & {
  event_type: "asyncio.executor.contention.detected";
} {
  return {
    event_type: "asyncio.executor.contention.detected",
    executor_id: "e-1",
    executor_kind: "Thread",
    max_workers: 4,
    sequence: 3,
    snapshot: {},
    active_workers: 4,
    utilization_ratio: 1.0,
    ...overrides,
  };
}

export function makeLatencySpike(
  overrides: Partial<ExecutorLatencySpikeDetectedPayload> = {},
): ExecutorLatencySpikeDetectedPayload & {
  event_type: "asyncio.executor.latency.spike.detected";
} {
  return {
    event_type: "asyncio.executor.latency.spike.detected",
    executor_id: "e-1",
    executor_kind: "Thread",
    max_workers: 4,
    sequence: 4,
    snapshot: {},
    submission_latency_seconds: 0.5,
    threshold_seconds: 0.25,
    active_workers: 4,
    ...overrides,
  };
}

export type AnyExecutorPayload = ExecutorActivityEventPayload;
