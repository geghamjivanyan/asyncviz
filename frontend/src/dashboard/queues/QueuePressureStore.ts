/**
 * Zustand store for the queue pressure dashboard panel.
 *
 * Owns:
 *   * the latest per-queue :class:`QueueMetricsRecord` map
 *   * a bounded marker ring (saturation / contention / pressure-change)
 *     for the timeline overlay
 *   * UI selection (currently-focused queue)
 *   * sequence + reconciliation stats
 *
 * Pure reducers (``reduceHydration``, ``reduceEventPayload``,
 * ``appendMarker``) live next to the actions so tests can exercise
 * them without a Zustand instance. Live updates flow through
 * :func:`applyEventPayload`; hydration uses :func:`hydrateSnapshot`.
 *
 * State is intentionally small: the projection layer derives
 * everything the views need from the per-queue records.
 */

import { create } from "zustand";
import type {
  QueueMetricsEngineSelfRecord,
  QueueMetricsEventPayload,
  QueueMetricsHydrationResponse,
  QueueMetricsRecord,
  QueueMetricsUpdatedPayload,
  QueuePressureChangedPayload,
  QueueContentionDetectedPayload,
  QueuePressureMarker,
  QueueSaturationDetectedPayload,
} from "@/dashboard/queues/models/QueuePressureModels";
import { deriveSeverity } from "@/dashboard/queues/QueuePressureSeverity";

/** Capacity of the rolling marker buffer. Bounded so a noisy queue
 *  can't grow the store without limit. */
export const DEFAULT_MARKER_CAPACITY = 512;

// ── reconciliation stats ────────────────────────────────────────────────

export interface QueuePressureStoreStats {
  hydrationsApplied: number;
  eventsApplied: number;
  eventsDropped: number;
  markersAppended: number;
  markersEvicted: number;
  lastEventAtMs: number;
}

const INITIAL_STATS: QueuePressureStoreStats = {
  hydrationsApplied: 0,
  eventsApplied: 0,
  eventsDropped: 0,
  markersAppended: 0,
  markersEvicted: 0,
  lastEventAtMs: 0,
};

// ── store shape ─────────────────────────────────────────────────────────

export type QueuePressureStoreStatus = "idle" | "loading" | "ready" | "error";

export interface QueuePressureStoreState {
  recordsById: Record<string, QueueMetricsRecord>;
  /** Insertion-order list — keeps the panel's queue list stable across renders. */
  queueIds: string[];
  selfMetrics: QueueMetricsEngineSelfRecord | null;
  config: Record<string, unknown>;
  markers: QueuePressureMarker[];
  markerCapacity: number;
  selectedQueueId: string | null;
  status: QueuePressureStoreStatus;
  errorMessage: string | null;
  lastSequence: number;
  stats: QueuePressureStoreStats;

  // ── actions ────────────────────────────────────────────────────────
  hydrateSnapshot: (snapshot: QueueMetricsHydrationResponse) => void;
  applyEventPayload: (payload: QueueMetricsEventPayload) => void;
  setSelectedQueue: (queueId: string | null) => void;
  markLoading: () => void;
  markError: (message: string) => void;
  setMarkerCapacity: (capacity: number) => void;
  reset: () => void;
}

// ── pure reducer helpers ────────────────────────────────────────────────

interface HydrationResult {
  recordsById: Record<string, QueueMetricsRecord>;
  queueIds: string[];
}

export function reduceHydration(snapshot: QueueMetricsHydrationResponse): HydrationResult {
  const recordsById: Record<string, QueueMetricsRecord> = {};
  const queueIds: string[] = [];
  for (const record of snapshot.queues) {
    recordsById[record.queue_id] = record;
    queueIds.push(record.queue_id);
  }
  return { recordsById, queueIds };
}

/**
 * Apply one engine-emitted aggregate payload to the records map.
 *
 * For ``metrics.updated`` we synthesize a record from the flat payload
 * fields (the wire payload carries every aggregate inline). For the
 * other three event types we update only the fields the payload knows
 * about — leaving the existing record's throughput / wait digests
 * intact.
 */
export function reduceEventPayload(
  records: Record<string, QueueMetricsRecord>,
  payload: QueueMetricsEventPayload,
): Record<string, QueueMetricsRecord> | null {
  const existing = records[payload.queue_id];
  switch (payload.event_type) {
    case "asyncio.queue.metrics.updated":
      return {
        ...records,
        [payload.queue_id]: recordFromUpdatedPayload(existing, payload),
      };
    case "asyncio.queue.pressure.changed":
      if (!existing) return null;
      return {
        ...records,
        [payload.queue_id]: applyPressureChange(existing, payload),
      };
    case "asyncio.queue.contention.detected":
      if (!existing) return null;
      return {
        ...records,
        [payload.queue_id]: applyContention(existing, payload),
      };
    case "asyncio.queue.saturation.detected":
      if (!existing) return null;
      return {
        ...records,
        [payload.queue_id]: applySaturation(existing, payload),
      };
  }
}

/** Build a marker from any engine-emitted payload, or ``null`` for
 *  ``metrics.updated`` (those don't need a timeline marker). */
export function markerFromPayload(
  payload: QueueMetricsEventPayload,
  monotonicNs: number,
): QueuePressureMarker | null {
  switch (payload.event_type) {
    case "asyncio.queue.pressure.changed":
      return {
        id: `pressure-${payload.queue_id}-${payload.sequence}`,
        queueId: payload.queue_id,
        kind: "pressure-change",
        severity: deriveSeverity(payload.new_level, false),
        monotonicNs,
        label: `${payload.previous_level} → ${payload.new_level}`,
        detail: `score=${payload.pressure_score.toFixed(2)}`,
      };
    case "asyncio.queue.contention.detected":
      return {
        id: `contention-${payload.queue_id}-${payload.sequence}`,
        queueId: payload.queue_id,
        kind: "contention",
        severity: "warning",
        monotonicNs,
        label: `${payload.contention_kind} contention`,
        detail: `blocked_p=${payload.blocked_producers} blocked_c=${payload.blocked_consumers}`,
      };
    case "asyncio.queue.saturation.detected":
      return {
        id: `saturation-${payload.queue_id}-${payload.sequence}`,
        queueId: payload.queue_id,
        kind: "saturation",
        severity: "saturated",
        monotonicNs,
        label: `Saturated (${(payload.occupancy_ratio * 100).toFixed(0)}%)`,
        detail: `size=${payload.current_size}/${payload.maxsize}`,
      };
    case "asyncio.queue.metrics.updated":
      return null;
  }
}

/** Append-and-cap. Returns the new buffer + how many entries were evicted. */
export function appendMarker(
  buffer: ReadonlyArray<QueuePressureMarker>,
  marker: QueuePressureMarker,
  capacity: number,
): { next: QueuePressureMarker[]; evicted: number } {
  const next = [...buffer, marker];
  const overflow = Math.max(0, next.length - capacity);
  if (overflow > 0) next.splice(0, overflow);
  return { next, evicted: overflow };
}

// ── reducer internals ───────────────────────────────────────────────────

function recordFromUpdatedPayload(
  existing: QueueMetricsRecord | undefined,
  payload: QueueMetricsUpdatedPayload,
): QueueMetricsRecord {
  const base = existing ?? scaffoldRecord(payload.queue_id, payload.queue_kind, payload.maxsize);
  return {
    ...base,
    queue_id: payload.queue_id,
    queue_kind: payload.queue_kind,
    maxsize: payload.maxsize,
    sequence: payload.sequence,
    occupancy: {
      ...base.occupancy,
      current_size: payload.current_size,
      peak_size: payload.peak_size,
      occupancy_ratio: payload.occupancy_ratio,
      mean_occupancy: payload.mean_occupancy,
    },
    throughput: {
      ...base.throughput,
      put_count: payload.put_count,
      get_count: payload.get_count,
      put_rate: payload.put_rate,
      get_rate: payload.get_rate,
      producer_consumer_delta: payload.producer_consumer_delta,
      cancelled_count: payload.cancelled_count,
    },
    contention: {
      ...base.contention,
      blocked_producers: payload.blocked_producers,
      blocked_consumers: payload.blocked_consumers,
      blocked_put_count: payload.blocked_put_count,
      blocked_get_count: payload.blocked_get_count,
    },
    pressure: {
      ...base.pressure,
      pressure_score: payload.pressure_score,
      level: payload.pressure_level,
    },
  };
}

function applyPressureChange(
  existing: QueueMetricsRecord,
  payload: QueuePressureChangedPayload,
): QueueMetricsRecord {
  return {
    ...existing,
    sequence: payload.sequence,
    pressure: {
      ...existing.pressure,
      pressure_score: payload.pressure_score,
      level: payload.new_level,
    },
    occupancy: {
      ...existing.occupancy,
      occupancy_ratio: payload.occupancy_ratio,
    },
    contention: {
      ...existing.contention,
      blocked_producers: payload.blocked_producers,
      blocked_consumers: payload.blocked_consumers,
    },
  };
}

function applyContention(
  existing: QueueMetricsRecord,
  payload: QueueContentionDetectedPayload,
): QueueMetricsRecord {
  return {
    ...existing,
    sequence: payload.sequence,
    contention: {
      ...existing.contention,
      blocked_producers: payload.blocked_producers,
      blocked_consumers: payload.blocked_consumers,
      blocked_put_count: payload.blocked_put_total,
      blocked_get_count: payload.blocked_get_total,
    },
  };
}

function applySaturation(
  existing: QueueMetricsRecord,
  payload: QueueSaturationDetectedPayload,
): QueueMetricsRecord {
  return {
    ...existing,
    sequence: payload.sequence,
    occupancy: {
      ...existing.occupancy,
      occupancy_ratio: payload.occupancy_ratio,
      current_size: payload.current_size,
    },
    pressure: {
      ...existing.pressure,
      saturated: true,
      saturation_ratio: Math.max(existing.pressure.saturation_ratio, payload.occupancy_ratio),
    },
  };
}

function scaffoldRecord(queueId: string, queueKind: string, maxsize: number): QueueMetricsRecord {
  return {
    queue_id: queueId,
    queue_kind: queueKind,
    maxsize,
    sequence: 0,
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
  };
}

// ── Zustand instance ────────────────────────────────────────────────────

export const useQueuePressureStore = create<QueuePressureStoreState>((set, get) => ({
  recordsById: {},
  queueIds: [],
  selfMetrics: null,
  config: {},
  markers: [],
  markerCapacity: DEFAULT_MARKER_CAPACITY,
  selectedQueueId: null,
  status: "idle",
  errorMessage: null,
  lastSequence: 0,
  stats: INITIAL_STATS,

  hydrateSnapshot(snapshot) {
    const reduced = reduceHydration(snapshot);
    set((state) => ({
      recordsById: reduced.recordsById,
      queueIds: reduced.queueIds,
      selfMetrics: snapshot.self_metrics,
      config: snapshot.config,
      status: "ready",
      errorMessage: null,
      stats: {
        ...state.stats,
        hydrationsApplied: state.stats.hydrationsApplied + 1,
        lastEventAtMs: Date.now(),
      },
    }));
  },

  applyEventPayload(payload) {
    const state = get();
    const records = state.recordsById;
    const reduced = reduceEventPayload(records, payload);
    if (reduced === null) {
      set((s) => ({
        stats: { ...s.stats, eventsDropped: s.stats.eventsDropped + 1 },
      }));
      return;
    }
    // Use timestamp from payload's monotonic source when present; the
    // wire shape doesn't carry it on payload itself (it lives on the
    // envelope), so we synthesize a monotonically-increasing pseudo-time
    // from ``performance.now`` for marker ordering. The real monotonic
    // value gets backfilled by the websocket bridge.
    const monotonicNs =
      typeof performance !== "undefined"
        ? Math.floor(performance.now() * 1_000_000)
        : Date.now() * 1_000_000;
    const marker = markerFromPayload(payload, monotonicNs);
    const queueIds =
      payload.queue_id in records ? state.queueIds : [...state.queueIds, payload.queue_id];
    if (marker !== null) {
      const { next: markers, evicted } = appendMarker(state.markers, marker, state.markerCapacity);
      set((s) => ({
        recordsById: reduced,
        queueIds,
        markers,
        status: s.status === "idle" ? "ready" : s.status,
        lastSequence: Math.max(s.lastSequence, payload.sequence),
        stats: {
          ...s.stats,
          eventsApplied: s.stats.eventsApplied + 1,
          markersAppended: s.stats.markersAppended + 1,
          markersEvicted: s.stats.markersEvicted + evicted,
          lastEventAtMs: Date.now(),
        },
      }));
      return;
    }
    set((s) => ({
      recordsById: reduced,
      queueIds,
      status: s.status === "idle" ? "ready" : s.status,
      lastSequence: Math.max(s.lastSequence, payload.sequence),
      stats: {
        ...s.stats,
        eventsApplied: s.stats.eventsApplied + 1,
        lastEventAtMs: Date.now(),
      },
    }));
  },

  setSelectedQueue(queueId) {
    set({ selectedQueueId: queueId });
  },

  markLoading() {
    set({ status: "loading", errorMessage: null });
  },

  markError(message) {
    set({ status: "error", errorMessage: message });
  },

  setMarkerCapacity(capacity) {
    if (capacity < 1) return;
    set({ markerCapacity: capacity });
  },

  reset() {
    set({
      recordsById: {},
      queueIds: [],
      selfMetrics: null,
      config: {},
      markers: [],
      selectedQueueId: null,
      status: "idle",
      errorMessage: null,
      lastSequence: 0,
      stats: INITIAL_STATS,
    });
  },
}));
