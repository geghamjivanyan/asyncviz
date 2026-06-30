/**
 * Zustand store for the executor activity dashboard panel.
 *
 * Owns:
 *   * the latest per-executor :class:`ExecutorMetricsRecord` map
 *   * a bounded marker ring (saturation / contention / latency-spike)
 *     for the timeline overlay
 *   * UI selection (currently-focused executor)
 *   * sequence + reconciliation stats
 *
 * Pure reducers live alongside the actions so tests can exercise them
 * without a Zustand instance. Live and replay both flow through the
 * same :func:`applyEventPayload` reducer.
 */

import { create } from "zustand";
import type {
  ExecutorActivityEventPayload,
  ExecutorActivityHydrationResponse,
  ExecutorActivityMarker,
  ExecutorContentionDetectedPayload,
  ExecutorEngineSelfRecord,
  ExecutorLatencySpikeDetectedPayload,
  ExecutorMetricsRecord,
  ExecutorMetricsUpdatedPayload,
  ExecutorSaturationChangedPayload,
} from "@/dashboard/executors/models/ExecutorActivityModels";
import { deriveSeverity } from "@/dashboard/executors/ExecutorActivitySeverity";

/** Capacity of the rolling marker buffer. */
export const DEFAULT_MARKER_CAPACITY = 512;

// ── reconciliation stats ────────────────────────────────────────────────

export interface ExecutorActivityStoreStats {
  hydrationsApplied: number;
  eventsApplied: number;
  eventsDropped: number;
  markersAppended: number;
  markersEvicted: number;
  lastEventAtMs: number;
}

const INITIAL_STATS: ExecutorActivityStoreStats = {
  hydrationsApplied: 0,
  eventsApplied: 0,
  eventsDropped: 0,
  markersAppended: 0,
  markersEvicted: 0,
  lastEventAtMs: 0,
};

export type ExecutorActivityStoreStatus = "idle" | "loading" | "ready" | "error";

export interface ExecutorActivityStoreState {
  recordsById: Record<string, ExecutorMetricsRecord>;
  /** Insertion-order list — keeps the panel ordering stable across renders. */
  executorIds: string[];
  selfMetrics: ExecutorEngineSelfRecord | null;
  config: Record<string, unknown>;
  markers: ExecutorActivityMarker[];
  markerCapacity: number;
  selectedExecutorId: string | null;
  status: ExecutorActivityStoreStatus;
  errorMessage: string | null;
  lastSequence: number;
  stats: ExecutorActivityStoreStats;

  hydrateSnapshot: (snapshot: ExecutorActivityHydrationResponse) => void;
  applyEventPayload: (payload: ExecutorActivityEventPayload) => void;
  setSelectedExecutor: (executorId: string | null) => void;
  markLoading: () => void;
  markError: (message: string) => void;
  setMarkerCapacity: (capacity: number) => void;
  reset: () => void;
}

// ── pure reducer helpers ────────────────────────────────────────────────

interface HydrationResult {
  recordsById: Record<string, ExecutorMetricsRecord>;
  executorIds: string[];
}

export function reduceHydration(snapshot: ExecutorActivityHydrationResponse): HydrationResult {
  const recordsById: Record<string, ExecutorMetricsRecord> = {};
  const executorIds: string[] = [];
  for (const record of snapshot.executors) {
    recordsById[record.executor_id] = record;
    executorIds.push(record.executor_id);
  }
  return { recordsById, executorIds };
}

function scaffoldRecord(
  executorId: string,
  executorKind: ExecutorMetricsRecord["executor_kind"],
  maxWorkers: number | null,
): ExecutorMetricsRecord {
  return {
    executor_id: executorId,
    executor_kind: executorKind,
    max_workers: maxWorkers,
    sequence: 0,
    utilization: {
      active_workers: 0,
      peak_active_workers: 0,
      max_workers: maxWorkers,
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
    submission_latency: {
      count: 0,
      mean_seconds: 0,
      p50_seconds: 0,
      p95_seconds: 0,
      p99_seconds: 0,
      max_seconds: 0,
    },
    execution_duration: {
      count: 0,
      mean_seconds: 0,
      p50_seconds: 0,
      p95_seconds: 0,
      p99_seconds: 0,
      max_seconds: 0,
    },
  };
}

function applyUpdated(
  existing: ExecutorMetricsRecord | undefined,
  payload: ExecutorMetricsUpdatedPayload,
): ExecutorMetricsRecord {
  const base =
    existing ?? scaffoldRecord(payload.executor_id, payload.executor_kind, payload.max_workers);
  return {
    ...base,
    executor_id: payload.executor_id,
    executor_kind: payload.executor_kind,
    max_workers: payload.max_workers,
    sequence: payload.sequence,
    utilization: {
      ...base.utilization,
      active_workers: payload.active_workers,
      peak_active_workers: payload.peak_active_workers,
      max_workers: payload.max_workers,
      utilization_ratio: payload.utilization_ratio,
      mean_utilization: payload.mean_utilization,
    },
    throughput: {
      ...base.throughput,
      submissions: payload.submissions,
      completions: payload.completions,
      failures: payload.failures,
      cancellations: payload.cancellations,
      submission_rate: payload.submission_rate,
      completion_rate: payload.completion_rate,
      backlog: payload.backlog,
    },
    saturation: {
      ...base.saturation,
      saturation_score: payload.saturation_score,
      level: payload.saturation_level,
    },
    submission_latency: {
      ...base.submission_latency,
      mean_seconds: payload.mean_submission_latency_seconds,
      p95_seconds: payload.p95_submission_latency_seconds,
    },
    execution_duration: {
      ...base.execution_duration,
      mean_seconds: payload.mean_execution_duration_seconds,
      p95_seconds: payload.p95_execution_duration_seconds,
    },
  };
}

function applySaturationChange(
  existing: ExecutorMetricsRecord,
  payload: ExecutorSaturationChangedPayload,
): ExecutorMetricsRecord {
  return {
    ...existing,
    sequence: payload.sequence,
    utilization: {
      ...existing.utilization,
      utilization_ratio: payload.utilization_ratio,
    },
    throughput: { ...existing.throughput, backlog: payload.backlog },
    saturation: {
      ...existing.saturation,
      saturation_score: payload.saturation_score,
      level: payload.new_level,
    },
  };
}

function applyContention(
  existing: ExecutorMetricsRecord,
  payload: ExecutorContentionDetectedPayload,
): ExecutorMetricsRecord {
  return {
    ...existing,
    sequence: payload.sequence,
    utilization: {
      ...existing.utilization,
      active_workers: payload.active_workers,
      utilization_ratio: payload.utilization_ratio,
    },
  };
}

function applyLatencySpike(
  existing: ExecutorMetricsRecord,
  payload: ExecutorLatencySpikeDetectedPayload,
): ExecutorMetricsRecord {
  return {
    ...existing,
    sequence: payload.sequence,
    utilization: {
      ...existing.utilization,
      active_workers: payload.active_workers,
    },
    submission_latency: {
      ...existing.submission_latency,
      max_seconds: Math.max(
        existing.submission_latency.max_seconds,
        payload.submission_latency_seconds,
      ),
    },
  };
}

/**
 * Apply one engine-emitted aggregate payload to the records map.
 *
 * For ``metrics.updated`` we upsert; the other three event types
 * patch only the fields they know about — leaving throughput +
 * latency digests intact when those events arrive in isolation.
 */
export function reduceEventPayload(
  records: Record<string, ExecutorMetricsRecord>,
  payload: ExecutorActivityEventPayload,
): Record<string, ExecutorMetricsRecord> | null {
  const existing = records[payload.executor_id];
  switch (payload.event_type) {
    case "asyncio.executor.metrics.updated":
      return {
        ...records,
        [payload.executor_id]: applyUpdated(existing, payload),
      };
    case "asyncio.executor.saturation.changed":
      if (!existing) return null;
      return {
        ...records,
        [payload.executor_id]: applySaturationChange(existing, payload),
      };
    case "asyncio.executor.contention.detected":
      if (!existing) return null;
      return {
        ...records,
        [payload.executor_id]: applyContention(existing, payload),
      };
    case "asyncio.executor.latency.spike.detected":
      if (!existing) return null;
      return {
        ...records,
        [payload.executor_id]: applyLatencySpike(existing, payload),
      };
  }
}

/** Build a marker from any engine-emitted payload, or ``null`` for
 *  ``metrics.updated`` (those don't need a timeline marker). */
export function markerFromPayload(
  payload: ExecutorActivityEventPayload,
  monotonicNs: number,
): ExecutorActivityMarker | null {
  switch (payload.event_type) {
    case "asyncio.executor.saturation.changed":
      return {
        id: `saturation-${payload.executor_id}-${payload.sequence}`,
        executorId: payload.executor_id,
        kind: "saturation-changed",
        severity: deriveSeverity({
          level: payload.new_level,
          utilizationRatio: payload.utilization_ratio,
          backlog: payload.backlog,
        }),
        monotonicNs,
        label: `${payload.previous_level} → ${payload.new_level}`,
        detail: `score=${payload.saturation_score.toFixed(2)}`,
      };
    case "asyncio.executor.contention.detected":
      return {
        id: `contention-${payload.executor_id}-${payload.sequence}`,
        executorId: payload.executor_id,
        kind: "contention",
        severity: "warning",
        monotonicNs,
        label: `${payload.active_workers} active`,
        detail: `util=${(payload.utilization_ratio * 100).toFixed(0)}%`,
      };
    case "asyncio.executor.latency.spike.detected":
      return {
        id: `latency-${payload.executor_id}-${payload.sequence}`,
        executorId: payload.executor_id,
        kind: "latency-spike",
        severity: "warning",
        monotonicNs,
        label: `${(payload.submission_latency_seconds * 1000).toFixed(0)}ms wait`,
        detail: `threshold=${(payload.threshold_seconds * 1000).toFixed(0)}ms`,
      };
    case "asyncio.executor.metrics.updated":
      return null;
  }
}

export function appendMarker(
  buffer: ReadonlyArray<ExecutorActivityMarker>,
  marker: ExecutorActivityMarker,
  capacity: number,
): { next: ExecutorActivityMarker[]; evicted: number } {
  const next = [...buffer, marker];
  const overflow = Math.max(0, next.length - capacity);
  if (overflow > 0) next.splice(0, overflow);
  return { next, evicted: overflow };
}

// ── Zustand instance ────────────────────────────────────────────────────

export const useExecutorActivityStore = create<ExecutorActivityStoreState>((set, get) => ({
  recordsById: {},
  executorIds: [],
  selfMetrics: null,
  config: {},
  markers: [],
  markerCapacity: DEFAULT_MARKER_CAPACITY,
  selectedExecutorId: null,
  status: "idle",
  errorMessage: null,
  lastSequence: 0,
  stats: INITIAL_STATS,

  hydrateSnapshot(snapshot) {
    const reduced = reduceHydration(snapshot);
    set((state) => ({
      recordsById: reduced.recordsById,
      executorIds: reduced.executorIds,
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
    const reduced = reduceEventPayload(state.recordsById, payload);
    if (reduced === null) {
      set((s) => ({
        stats: { ...s.stats, eventsDropped: s.stats.eventsDropped + 1 },
      }));
      return;
    }
    const monotonicNs =
      typeof performance !== "undefined"
        ? Math.floor(performance.now() * 1_000_000)
        : Date.now() * 1_000_000;
    const marker = markerFromPayload(payload, monotonicNs);
    const executorIds =
      payload.executor_id in state.recordsById
        ? state.executorIds
        : [...state.executorIds, payload.executor_id];
    if (marker !== null) {
      const { next: markers, evicted } = appendMarker(state.markers, marker, state.markerCapacity);
      set((s) => ({
        recordsById: reduced,
        executorIds,
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
      executorIds,
      status: s.status === "idle" ? "ready" : s.status,
      lastSequence: Math.max(s.lastSequence, payload.sequence),
      stats: {
        ...s.stats,
        eventsApplied: s.stats.eventsApplied + 1,
        lastEventAtMs: Date.now(),
      },
    }));
  },

  setSelectedExecutor(executorId) {
    set({ selectedExecutorId: executorId });
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
      executorIds: [],
      selfMetrics: null,
      config: {},
      markers: [],
      selectedExecutorId: null,
      status: "idle",
      errorMessage: null,
      lastSequence: 0,
      stats: INITIAL_STATS,
    });
  },
}));
