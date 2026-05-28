/**
 * Wire + view models for the queue pressure visualization layer.
 *
 * Mirrors the backend types in
 * :mod:`asyncviz.instrumentation.queue.metrics.queue_metrics_models`.
 * Kept side-effect-free + dependency-free so the projection / renderer /
 * store layers can import them without pulling React in.
 *
 * Two pyramids live in this file:
 *
 *   * **Wire-shape records** — what arrives over the websocket / REST.
 *     Match the backend dataclass layouts exactly; never rename fields
 *     without bumping the protocol.
 *   * **View-shape models** — what the panel + overlays read. Adds
 *     derived fields like ``severity`` + ``displayName`` that the
 *     renderer needs but don't belong on the wire.
 */

// ── shared ──────────────────────────────────────────────────────────────

/** Pressure band reported by the backend scorer. Single source of truth. */
export type QueuePressureLevel = "calm" | "warning" | "critical";

/** Visual severity bucket — overlays + cards key colors off this. */
export type QueuePressureSeverity =
  | "calm"
  | "warning"
  | "critical"
  | "saturated";

/** Kind reported by ``asyncio.queue.contention.detected``. */
export type QueueContentionKind = "producers" | "consumers" | "both";

// ── wire-shape: per-queue sub-records ───────────────────────────────────

export interface QueueOccupancyRecord {
  current_size: number;
  peak_size: number;
  occupancy_ratio: number;
  mean_occupancy: number;
  sample_count: number;
}

export interface QueueThroughputRecord {
  put_count: number;
  get_count: number;
  put_rate: number;
  get_rate: number;
  producer_consumer_delta: number;
  task_done_count: number;
  nowait_put_count: number;
  nowait_get_count: number;
  cancelled_count: number;
}

export interface QueueContentionRecord {
  blocked_producers: number;
  blocked_consumers: number;
  blocked_put_count: number;
  blocked_get_count: number;
  full_wait_count: number;
  empty_wait_count: number;
  cancelled_count: number;
  peak_blocked_producers: number;
  peak_blocked_consumers: number;
}

export interface QueuePressureRecord {
  pressure_score: number;
  level: QueuePressureLevel;
  saturation_ratio: number;
  saturated: boolean;
  backlog_velocity: number;
}

export interface QueueWaitRecord {
  count: number;
  mean_seconds: number;
  p50_seconds: number;
  p95_seconds: number;
  p99_seconds: number;
  max_seconds: number;
}

export interface QueueMetricsRecord {
  queue_id: string;
  queue_kind: string;
  maxsize: number;
  sequence: number;
  occupancy: QueueOccupancyRecord;
  throughput: QueueThroughputRecord;
  contention: QueueContentionRecord;
  pressure: QueuePressureRecord;
  put_wait: QueueWaitRecord;
  get_wait: QueueWaitRecord;
}

// ── engine-level / snapshot wire shapes ─────────────────────────────────

export interface QueueMetricsEngineSelfRecord {
  events_observed: number;
  events_ignored: number;
  events_dropped: number;
  updates_emitted: number;
  pressure_transitions: number;
  contention_detections: number;
  saturation_detections: number;
  tracked_queues: number;
  queues_evicted: number;
  recursion_skips: number;
}

export interface QueueMetricsSnapshot {
  queues: QueueMetricsRecord[];
  self_metrics: QueueMetricsEngineSelfRecord;
  config: Record<string, unknown>;
  trace_enabled?: boolean;
  trace_count?: number;
  recent_trace?: ReadonlyArray<{
    kind: string;
    detail: string;
    at_monotonic: number;
  }>;
}

// ── wire-shape: engine-emitted aggregate events ─────────────────────────

export interface QueueMetricsUpdatedPayload {
  queue_id: string;
  queue_kind: string;
  maxsize: number;
  sequence: number;
  snapshot: Record<string, unknown>;
  current_size: number;
  peak_size: number;
  occupancy_ratio: number;
  mean_occupancy: number;
  put_rate: number;
  get_rate: number;
  put_count: number;
  get_count: number;
  producer_consumer_delta: number;
  blocked_producers: number;
  blocked_consumers: number;
  blocked_put_count: number;
  blocked_get_count: number;
  cancelled_count: number;
  pressure_score: number;
  pressure_level: QueuePressureLevel;
}

export interface QueuePressureChangedPayload {
  queue_id: string;
  queue_kind: string;
  maxsize: number;
  sequence: number;
  snapshot: Record<string, unknown>;
  previous_level: QueuePressureLevel;
  new_level: QueuePressureLevel;
  pressure_score: number;
  occupancy_ratio: number;
  blocked_producers: number;
  blocked_consumers: number;
}

export interface QueueContentionDetectedPayload {
  queue_id: string;
  queue_kind: string;
  maxsize: number;
  sequence: number;
  snapshot: Record<string, unknown>;
  blocked_producers: number;
  blocked_consumers: number;
  blocked_put_total: number;
  blocked_get_total: number;
  contention_kind: QueueContentionKind;
}

export interface QueueSaturationDetectedPayload {
  queue_id: string;
  queue_kind: string;
  maxsize: number;
  sequence: number;
  snapshot: Record<string, unknown>;
  occupancy_ratio: number;
  current_size: number;
  threshold: number;
}

/** Discriminated union of every queue-metrics wire payload. */
export type QueueMetricsEventPayload =
  | ({ event_type: "asyncio.queue.metrics.updated" } & QueueMetricsUpdatedPayload)
  | ({ event_type: "asyncio.queue.pressure.changed" } & QueuePressureChangedPayload)
  | ({ event_type: "asyncio.queue.contention.detected" } & QueueContentionDetectedPayload)
  | ({ event_type: "asyncio.queue.saturation.detected" } & QueueSaturationDetectedPayload);

/** Canonical list of wire event types — mirrors the backend tuple. */
export const QUEUE_METRICS_EVENT_TYPES = [
  "asyncio.queue.metrics.updated",
  "asyncio.queue.pressure.changed",
  "asyncio.queue.contention.detected",
  "asyncio.queue.saturation.detected",
] as const;

export type QueueMetricsEventType = (typeof QUEUE_METRICS_EVENT_TYPES)[number];

// ── REST hydration wire shape ────────────────────────────────────────────

export interface QueueMetricsHydrationResponse {
  queues: QueueMetricsRecord[];
  self_metrics: QueueMetricsEngineSelfRecord;
  config: Record<string, unknown>;
  trace_enabled: boolean;
  trace_count: number;
  recent_trace: ReadonlyArray<{
    kind: string;
    detail: string;
    at_monotonic: number;
  }>;
}

// ── view-shape (projection-layer output) ────────────────────────────────

/**
 * One renderable queue, ready for the panel + overlay. Combines the
 * latest aggregate record with derived display fields the views need.
 */
export interface QueuePressureView {
  queueId: string;
  queueKind: string;
  maxsize: number;
  sequence: number;
  /** Display name — falls back to the queue id when no human name is known. */
  displayName: string;
  severity: QueuePressureSeverity;
  level: QueuePressureLevel;
  pressureScore: number;
  occupancyRatio: number;
  currentSize: number;
  peakSize: number;
  meanOccupancy: number;
  putRate: number;
  getRate: number;
  putCount: number;
  getCount: number;
  producerConsumerDelta: number;
  blockedProducers: number;
  blockedConsumers: number;
  blockedPutCount: number;
  blockedGetCount: number;
  cancelledCount: number;
  saturated: boolean;
  saturationRatio: number;
  backlogVelocity: number;
  putWaitP95Seconds: number;
  getWaitP95Seconds: number;
  /** Monotonic ns of the last event applied to this queue's state. */
  lastObservedMonotonicNs: number;
}

// ── timeline marker view-shape ──────────────────────────────────────────

export type QueuePressureMarkerKind =
  | "pressure-change"
  | "contention"
  | "saturation";

/**
 * A timeline-overlay marker emitted when the engine reported a notable
 * transition. Drawn over the timeline canvas; positions are computed in
 * the geometry helpers.
 */
export interface QueuePressureMarker {
  id: string;
  queueId: string;
  kind: QueuePressureMarkerKind;
  severity: QueuePressureSeverity;
  monotonicNs: number;
  /** Short label used by the overlay tooltip + screen-reader announcement. */
  label: string;
  /** Optional secondary fact (e.g. blocked-producer count). */
  detail?: string;
}
