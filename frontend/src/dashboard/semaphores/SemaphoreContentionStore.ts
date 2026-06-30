/**
 * Zustand store for the semaphore contention dashboard panel.
 *
 * Owns:
 *   * a per-semaphore ``SemaphoreRecord`` map synthesized from the
 *     hydration baseline + the streamed event timeline.
 *   * a bounded marker ring (contention / saturation / wait-cancelled)
 *     for the timeline overlay.
 *   * UI selection (currently-focused semaphore).
 *   * sequence + reconciliation stats.
 *
 * Pure reducers (``reduceHydration``, ``reduceEventPayload``,
 * ``appendMarker``, ``markerFromPayload``) live next to the actions
 * so tests can exercise them without a Zustand instance.
 */

import { create } from "zustand";
import type {
  SemaphoreAcquiredPayload,
  SemaphoreContentionDetectedPayload,
  SemaphoreCreatedPayload,
  SemaphoreEventPayload,
  SemaphoreHydrationResponse,
  SemaphoreIdentityRecord,
  SemaphoreMetricsRecord,
  SemaphoreRecord,
  SemaphoreReleasedPayload,
  SemaphoreSnapshotRecord,
  SemaphoreContentionMarker,
  SemaphoreWaitCancelledPayload,
  SemaphoreAcquireStartedPayload,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export const DEFAULT_MARKER_CAPACITY = 512;

// ── reconciliation stats ────────────────────────────────────────────────

export interface SemaphoreContentionStoreStats {
  hydrationsApplied: number;
  eventsApplied: number;
  eventsDropped: number;
  markersAppended: number;
  markersEvicted: number;
  lastEventAtMs: number;
}

const INITIAL_STATS: SemaphoreContentionStoreStats = {
  hydrationsApplied: 0,
  eventsApplied: 0,
  eventsDropped: 0,
  markersAppended: 0,
  markersEvicted: 0,
  lastEventAtMs: 0,
};

export type SemaphoreContentionStoreStatus = "idle" | "loading" | "ready" | "error";

export interface SemaphoreContentionStoreState {
  recordsById: Record<string, SemaphoreRecord>;
  /** Insertion-order list — keeps the panel ordering stable across renders. */
  semaphoreIds: string[];
  selfMetrics: SemaphoreMetricsRecord | null;
  registrySize: number;
  registryFinalized: number;
  markers: SemaphoreContentionMarker[];
  markerCapacity: number;
  selectedSemaphoreId: string | null;
  status: SemaphoreContentionStoreStatus;
  errorMessage: string | null;
  lastSequence: number;
  stats: SemaphoreContentionStoreStats;

  hydrateSnapshot: (snapshot: SemaphoreHydrationResponse) => void;
  applyEventPayload: (payload: SemaphoreEventPayload) => void;
  setSelectedSemaphore: (semaphoreId: string | null) => void;
  markLoading: () => void;
  markError: (message: string) => void;
  setMarkerCapacity: (capacity: number) => void;
  reset: () => void;
}

// ── pure reducer helpers ────────────────────────────────────────────────

interface HydrationResult {
  recordsById: Record<string, SemaphoreRecord>;
  semaphoreIds: string[];
}

export function recordFromIdentity(identity: SemaphoreIdentityRecord): SemaphoreRecord {
  return {
    semaphoreId: identity.semaphore_id,
    semaphoreKind: identity.semaphore_kind,
    initialValue: identity.initial_value,
    boundValue: identity.bound_value,
    creatorTaskId: identity.creator_task_id,
    name: identity.name,
    // Hydration doesn't carry live state — fill it in as events arrive.
    currentValue: null,
    waiterCount: 0,
    acquireCount: 0,
    releaseCount: 0,
    blockedAcquireCount: 0,
    cancelledWaitCount: 0,
    peakWaiterCount: 0,
    meanWaitSeconds: 0,
    maxWaitSeconds: 0,
    sequence: 0,
  };
}

export function reduceHydration(snapshot: SemaphoreHydrationResponse): HydrationResult {
  const recordsById: Record<string, SemaphoreRecord> = {};
  const semaphoreIds: string[] = [];
  for (const identity of snapshot.semaphores) {
    recordsById[identity.semaphore_id] = recordFromIdentity(identity);
    semaphoreIds.push(identity.semaphore_id);
  }
  return { recordsById, semaphoreIds };
}

function scaffoldFromPayload(payload: SemaphoreEventPayload): SemaphoreRecord {
  const creator =
    payload.event_type === "asyncio.semaphore.created" ? payload.creator_task_id : null;
  const name = payload.event_type === "asyncio.semaphore.created" ? payload.name : null;
  return {
    semaphoreId: payload.semaphore_id,
    semaphoreKind: payload.semaphore_kind,
    initialValue: payload.initial_value,
    boundValue: payload.bound_value,
    creatorTaskId: creator,
    name,
    currentValue: null,
    waiterCount: 0,
    acquireCount: 0,
    releaseCount: 0,
    blockedAcquireCount: 0,
    cancelledWaitCount: 0,
    peakWaiterCount: 0,
    meanWaitSeconds: 0,
    maxWaitSeconds: 0,
    sequence: 0,
  };
}

function snapshotOf(payload: SemaphoreEventPayload): SemaphoreSnapshotRecord {
  const snap = payload.snapshot as Partial<SemaphoreSnapshotRecord> | undefined;
  return {
    current_value: Number.isFinite(snap?.current_value as number)
      ? (snap!.current_value as number)
      : 0,
    waiter_count: Number.isFinite(snap?.waiter_count as number)
      ? (snap!.waiter_count as number)
      : 0,
    initial_value: Number.isFinite(snap?.initial_value as number)
      ? (snap!.initial_value as number)
      : payload.initial_value,
    bound_value: typeof snap?.bound_value === "number" ? snap.bound_value : payload.bound_value,
  };
}

function applySnapshot(record: SemaphoreRecord, snap: SemaphoreSnapshotRecord): SemaphoreRecord {
  return {
    ...record,
    currentValue: snap.current_value,
    waiterCount: snap.waiter_count,
    peakWaiterCount: Math.max(record.peakWaiterCount, snap.waiter_count),
  };
}

function applyCreated(record: SemaphoreRecord, payload: SemaphoreCreatedPayload): SemaphoreRecord {
  const snap = snapshotOf(payload);
  return {
    ...applySnapshot(record, snap),
    semaphoreKind: payload.semaphore_kind,
    initialValue: payload.initial_value,
    boundValue: payload.bound_value,
    creatorTaskId: payload.creator_task_id,
    name: payload.name,
  };
}

function applyAcquireStarted(
  record: SemaphoreRecord,
  payload: SemaphoreAcquireStartedPayload,
): SemaphoreRecord {
  return applySnapshot(record, snapshotOf(payload));
}

function applyAcquired(
  record: SemaphoreRecord,
  payload: SemaphoreAcquiredPayload,
): SemaphoreRecord {
  const snap = snapshotOf(payload);
  const next = applySnapshot(record, snap);
  next.acquireCount = record.acquireCount + 1;
  if (payload.blocked) {
    next.blockedAcquireCount = record.blockedAcquireCount + 1;
    if (payload.wait_seconds !== null && Number.isFinite(payload.wait_seconds)) {
      const total = record.meanWaitSeconds * record.blockedAcquireCount;
      next.meanWaitSeconds = (total + payload.wait_seconds) / next.blockedAcquireCount;
      next.maxWaitSeconds = Math.max(record.maxWaitSeconds, payload.wait_seconds);
    }
  }
  return next;
}

function applyReleased(
  record: SemaphoreRecord,
  payload: SemaphoreReleasedPayload,
): SemaphoreRecord {
  const next = applySnapshot(record, snapshotOf(payload));
  next.releaseCount = record.releaseCount + 1;
  return next;
}

function applyContention(
  record: SemaphoreRecord,
  payload: SemaphoreContentionDetectedPayload,
): SemaphoreRecord {
  // The wire payload includes flat ``waiter_count`` + ``current_value``
  // that may be slightly newer than the embedded snapshot (the engine
  // counts the new waiter explicitly). Prefer the flat fields here.
  return {
    ...record,
    currentValue: payload.current_value,
    waiterCount: payload.waiter_count,
    peakWaiterCount: Math.max(record.peakWaiterCount, payload.waiter_count),
  };
}

function applyCancelled(
  record: SemaphoreRecord,
  payload: SemaphoreWaitCancelledPayload,
): SemaphoreRecord {
  const next = applySnapshot(record, snapshotOf(payload));
  next.cancelledWaitCount = record.cancelledWaitCount + 1;
  return next;
}

/**
 * Apply one engine-emitted payload to the records map.
 *
 * Always returns a fresh map (never mutates the input) so Zustand can
 * diff-render efficiently. Returns ``null`` only when the payload's
 * ``event_type`` doesn't match a known semaphore event — never on
 * "unknown semaphore" because we lazily scaffold the record from the
 * first event for that id (most useful when a semaphore is created
 * after hydration completes).
 */
export function reduceEventPayload(
  records: Record<string, SemaphoreRecord>,
  payload: SemaphoreEventPayload,
): Record<string, SemaphoreRecord> | null {
  const existing = records[payload.semaphore_id] ?? scaffoldFromPayload(payload);
  let next: SemaphoreRecord;
  switch (payload.event_type) {
    case "asyncio.semaphore.created":
      next = applyCreated(existing, payload);
      break;
    case "asyncio.semaphore.acquire.started":
      next = applyAcquireStarted(existing, payload);
      break;
    case "asyncio.semaphore.acquired":
      next = applyAcquired(existing, payload);
      break;
    case "asyncio.semaphore.released":
      next = applyReleased(existing, payload);
      break;
    case "asyncio.semaphore.contention.detected":
      next = applyContention(existing, payload);
      break;
    case "asyncio.semaphore.wait.cancelled":
      next = applyCancelled(existing, payload);
      break;
    default:
      return null;
  }
  next.sequence = existing.sequence + 1;
  return { ...records, [payload.semaphore_id]: next };
}

/** Build a marker for a payload, or ``null`` if the event doesn't warrant one. */
export function markerFromPayload(
  payload: SemaphoreEventPayload,
  monotonicNs: number,
): SemaphoreContentionMarker | null {
  switch (payload.event_type) {
    case "asyncio.semaphore.contention.detected":
      return {
        id: `contention-${payload.semaphore_id}-${monotonicNs}`,
        semaphoreId: payload.semaphore_id,
        kind: "contention",
        severity: "warning",
        monotonicNs,
        label: `${payload.waiter_count} waiter${payload.waiter_count === 1 ? "" : "s"}`,
        detail: `value=${payload.current_value}`,
      };
    case "asyncio.semaphore.wait.cancelled":
      return {
        id: `cancelled-${payload.semaphore_id}-${monotonicNs}`,
        semaphoreId: payload.semaphore_id,
        kind: "wait-cancelled",
        severity: "warning",
        monotonicNs,
        label: "Wait cancelled",
        detail:
          payload.wait_seconds !== null ? `${payload.wait_seconds.toFixed(2)}s waited` : undefined,
      };
    case "asyncio.semaphore.acquired": {
      // Synthetic "saturation cleared" hint: if this was a blocked
      // acquire that drained the last waiter, surface a saturation
      // marker — same wire schema as the queue's saturation overlay.
      const snap = snapshotOf(payload);
      if (payload.blocked && snap.current_value === 0 && snap.waiter_count > 0) {
        return {
          id: `saturation-${payload.semaphore_id}-${monotonicNs}`,
          semaphoreId: payload.semaphore_id,
          kind: "saturation",
          severity: "saturated",
          monotonicNs,
          label: "Saturated",
          detail: `${snap.waiter_count} waiting`,
        };
      }
      return null;
    }
    default:
      return null;
  }
}

/** Append-and-cap; returns the new buffer + the number of entries evicted. */
export function appendMarker(
  buffer: ReadonlyArray<SemaphoreContentionMarker>,
  marker: SemaphoreContentionMarker,
  capacity: number,
): { next: SemaphoreContentionMarker[]; evicted: number } {
  const next = [...buffer, marker];
  const overflow = Math.max(0, next.length - capacity);
  if (overflow > 0) next.splice(0, overflow);
  return { next, evicted: overflow };
}

// ── Zustand instance ────────────────────────────────────────────────────

export const useSemaphoreContentionStore = create<SemaphoreContentionStoreState>((set, get) => ({
  recordsById: {},
  semaphoreIds: [],
  selfMetrics: null,
  registrySize: 0,
  registryFinalized: 0,
  markers: [],
  markerCapacity: DEFAULT_MARKER_CAPACITY,
  selectedSemaphoreId: null,
  status: "idle",
  errorMessage: null,
  lastSequence: 0,
  stats: INITIAL_STATS,

  hydrateSnapshot(snapshot) {
    const reduced = reduceHydration(snapshot);
    set((state) => ({
      recordsById: reduced.recordsById,
      semaphoreIds: reduced.semaphoreIds,
      selfMetrics: snapshot.metrics,
      registrySize: snapshot.registry_size,
      registryFinalized: snapshot.registry_finalized,
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
    const semaphoreIds =
      payload.semaphore_id in state.recordsById
        ? state.semaphoreIds
        : [...state.semaphoreIds, payload.semaphore_id];
    if (marker !== null) {
      const { next: markers, evicted } = appendMarker(state.markers, marker, state.markerCapacity);
      set((s) => ({
        recordsById: reduced,
        semaphoreIds,
        markers,
        status: s.status === "idle" ? "ready" : s.status,
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
      semaphoreIds,
      status: s.status === "idle" ? "ready" : s.status,
      stats: {
        ...s.stats,
        eventsApplied: s.stats.eventsApplied + 1,
        lastEventAtMs: Date.now(),
      },
    }));
  },

  setSelectedSemaphore(semaphoreId) {
    set({ selectedSemaphoreId: semaphoreId });
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
      semaphoreIds: [],
      selfMetrics: null,
      registrySize: 0,
      registryFinalized: 0,
      markers: [],
      selectedSemaphoreId: null,
      status: "idle",
      errorMessage: null,
      lastSequence: 0,
      stats: INITIAL_STATS,
    });
  },
}));
