import type {
  QueueMetricsHydrationResponse,
  QueueMetricsRecord,
  QueueMetricsUpdatedPayload,
  QueuePressureChangedPayload,
  QueueContentionDetectedPayload,
  QueueSaturationDetectedPayload,
  QueueMetricsEngineSelfRecord,
} from "@/dashboard/queues/models/QueuePressureModels";

export function makeRecord(overrides: Partial<QueueMetricsRecord> = {}): QueueMetricsRecord {
  return {
    queue_id: "q-1",
    queue_kind: "Queue",
    maxsize: 10,
    sequence: 1,
    occupancy: {
      current_size: 0,
      peak_size: 0,
      occupancy_ratio: 0,
      mean_occupancy: 0,
      sample_count: 0,
    },
    throughput: {
      put_count: 0,
      get_count: 0,
      put_rate: 0,
      get_rate: 0,
      producer_consumer_delta: 0,
      task_done_count: 0,
      nowait_put_count: 0,
      nowait_get_count: 0,
      cancelled_count: 0,
    },
    contention: {
      blocked_producers: 0,
      blocked_consumers: 0,
      blocked_put_count: 0,
      blocked_get_count: 0,
      full_wait_count: 0,
      empty_wait_count: 0,
      cancelled_count: 0,
      peak_blocked_producers: 0,
      peak_blocked_consumers: 0,
    },
    pressure: {
      pressure_score: 0,
      level: "calm",
      saturation_ratio: 0,
      saturated: false,
      backlog_velocity: 0,
    },
    put_wait: {
      count: 0,
      mean_seconds: 0,
      p50_seconds: 0,
      p95_seconds: 0,
      p99_seconds: 0,
      max_seconds: 0,
    },
    get_wait: {
      count: 0,
      mean_seconds: 0,
      p50_seconds: 0,
      p95_seconds: 0,
      p99_seconds: 0,
      max_seconds: 0,
    },
    ...overrides,
  };
}

export function makeUpdated(
  overrides: Partial<QueueMetricsUpdatedPayload> = {},
): QueueMetricsUpdatedPayload & { event_type: "asyncio.queue.metrics.updated" } {
  return {
    event_type: "asyncio.queue.metrics.updated",
    queue_id: "q-1",
    queue_kind: "Queue",
    maxsize: 10,
    sequence: 1,
    snapshot: {},
    current_size: 0,
    peak_size: 0,
    occupancy_ratio: 0,
    mean_occupancy: 0,
    put_rate: 0,
    get_rate: 0,
    put_count: 0,
    get_count: 0,
    producer_consumer_delta: 0,
    blocked_producers: 0,
    blocked_consumers: 0,
    blocked_put_count: 0,
    blocked_get_count: 0,
    cancelled_count: 0,
    pressure_score: 0,
    pressure_level: "calm",
    ...overrides,
  };
}

export function makePressureChange(
  overrides: Partial<QueuePressureChangedPayload> = {},
): QueuePressureChangedPayload & { event_type: "asyncio.queue.pressure.changed" } {
  return {
    event_type: "asyncio.queue.pressure.changed",
    queue_id: "q-1",
    queue_kind: "Queue",
    maxsize: 10,
    sequence: 2,
    snapshot: {},
    previous_level: "calm",
    new_level: "warning",
    pressure_score: 0.7,
    occupancy_ratio: 0.5,
    blocked_producers: 0,
    blocked_consumers: 0,
    ...overrides,
  };
}

export function makeContention(
  overrides: Partial<QueueContentionDetectedPayload> = {},
): QueueContentionDetectedPayload & { event_type: "asyncio.queue.contention.detected" } {
  return {
    event_type: "asyncio.queue.contention.detected",
    queue_id: "q-1",
    queue_kind: "Queue",
    maxsize: 10,
    sequence: 3,
    snapshot: {},
    blocked_producers: 2,
    blocked_consumers: 0,
    blocked_put_total: 5,
    blocked_get_total: 0,
    contention_kind: "producers",
    ...overrides,
  };
}

export function makeSaturation(
  overrides: Partial<QueueSaturationDetectedPayload> = {},
): QueueSaturationDetectedPayload & { event_type: "asyncio.queue.saturation.detected" } {
  return {
    event_type: "asyncio.queue.saturation.detected",
    queue_id: "q-1",
    queue_kind: "Queue",
    maxsize: 10,
    sequence: 4,
    snapshot: {},
    occupancy_ratio: 0.95,
    current_size: 9,
    threshold: 0.9,
    ...overrides,
  };
}

export function makeSelfMetrics(
  overrides: Partial<QueueMetricsEngineSelfRecord> = {},
): QueueMetricsEngineSelfRecord {
  return {
    events_observed: 0,
    events_ignored: 0,
    events_dropped: 0,
    updates_emitted: 0,
    pressure_transitions: 0,
    contention_detections: 0,
    saturation_detections: 0,
    tracked_queues: 0,
    queues_evicted: 0,
    recursion_skips: 0,
    ...overrides,
  };
}

export function makeHydration(
  overrides: Partial<QueueMetricsHydrationResponse> = {},
): QueueMetricsHydrationResponse {
  return {
    queues: [],
    self_metrics: makeSelfMetrics(),
    config: {},
    trace_enabled: false,
    trace_count: 0,
    recent_trace: [],
    ...overrides,
  };
}
