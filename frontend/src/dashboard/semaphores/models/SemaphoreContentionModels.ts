/**
 * Wire + view models for the semaphore contention visualization layer.
 *
 * Mirrors the backend types in
 * :mod:`asyncviz.runtime.events.models.semaphore` and the registry
 * snapshot returned by ``GET /api/semaphores``. Kept dependency-free
 * so the projection / renderer / store layers can import without
 * pulling React in.
 */

// ── shared ──────────────────────────────────────────────────────────────

/** Backend semaphore kinds reported by the registry. */
export type SemaphoreKind = "Semaphore" | "BoundedSemaphore" | "subclass" | "unknown";

/** Visual severity bucket — cards + markers key colors off this. */
export type SemaphoreContentionSeverity = "calm" | "warning" | "critical" | "saturated";

// ── wire-shape: snapshot dict carried on every event ───────────────────

export interface SemaphoreSnapshotRecord {
  current_value: number;
  waiter_count: number;
  initial_value: number;
  bound_value: number | null;
}

// ── wire-shape: per-semaphore engine self-metrics ──────────────────────

export interface SemaphoreMetricsRecord {
  semaphores_registered: number;
  semaphores_finalized: number;
  events_emitted: number;
  events_dropped: number;
  acquire_events: number;
  release_events: number;
  cancelled_waits: number;
  contention_detections: number;
  blocked_acquires: number;
  recursion_skips: number;
}

// ── wire-shape: registry identity dict ──────────────────────────────────

export interface SemaphoreIdentityRecord {
  semaphore_id: string;
  semaphore_kind: SemaphoreKind;
  initial_value: number;
  bound_value: number | null;
  creator_task_id: string | null;
  name: string | null;
}

// ── wire-shape: REST hydration payload ──────────────────────────────────

export interface SemaphoreHydrationResponse {
  registry_size: number;
  registry_finalized: number;
  metrics: SemaphoreMetricsRecord;
  trace_enabled: boolean;
  trace_count: number;
  semaphores: SemaphoreIdentityRecord[];
}

// ── wire-shape: engine-emitted events ───────────────────────────────────

interface _SemaphoreEventBase {
  semaphore_id: string;
  semaphore_kind: SemaphoreKind;
  initial_value: number;
  bound_value: number | null;
  task_id: string | null;
  snapshot: SemaphoreSnapshotRecord | Record<string, unknown>;
}

export interface SemaphoreCreatedPayload extends _SemaphoreEventBase {
  event_type: "asyncio.semaphore.created";
  creator_task_id: string | null;
  name: string | null;
}

export interface SemaphoreAcquireStartedPayload extends _SemaphoreEventBase {
  event_type: "asyncio.semaphore.acquire.started";
  will_block: boolean;
}

export interface SemaphoreAcquiredPayload extends _SemaphoreEventBase {
  event_type: "asyncio.semaphore.acquired";
  blocked: boolean;
  wait_seconds: number | null;
}

export interface SemaphoreReleasedPayload extends _SemaphoreEventBase {
  event_type: "asyncio.semaphore.released";
}

export interface SemaphoreContentionDetectedPayload extends _SemaphoreEventBase {
  event_type: "asyncio.semaphore.contention.detected";
  waiter_count: number;
  current_value: number;
}

export interface SemaphoreWaitCancelledPayload extends _SemaphoreEventBase {
  event_type: "asyncio.semaphore.wait.cancelled";
  wait_seconds: number | null;
}

/** Discriminated union of every semaphore wire payload. */
export type SemaphoreEventPayload =
  | SemaphoreCreatedPayload
  | SemaphoreAcquireStartedPayload
  | SemaphoreAcquiredPayload
  | SemaphoreReleasedPayload
  | SemaphoreContentionDetectedPayload
  | SemaphoreWaitCancelledPayload;

/** Canonical event-type list — mirrors the backend tuple exactly. */
export const SEMAPHORE_EVENT_TYPES = [
  "asyncio.semaphore.created",
  "asyncio.semaphore.acquire.started",
  "asyncio.semaphore.acquired",
  "asyncio.semaphore.released",
  "asyncio.semaphore.contention.detected",
  "asyncio.semaphore.wait.cancelled",
] as const;

export type SemaphoreEventType = (typeof SEMAPHORE_EVENT_TYPES)[number];

// ── per-semaphore runtime state (store internal) ───────────────────────

/**
 * Live per-semaphore state synthesized from streamed events. Unlike
 * queues, the backend registry doesn't snapshot ``current_value`` /
 * ``waiter_count`` on demand — those are derived purely from the
 * websocket stream + the identity hydration baseline.
 */
export interface SemaphoreRecord {
  semaphoreId: string;
  semaphoreKind: SemaphoreKind;
  initialValue: number;
  boundValue: number | null;
  creatorTaskId: string | null;
  name: string | null;
  /** Last-observed permit count. ``null`` until the first event arrives. */
  currentValue: number | null;
  /** Last-observed blocked-waiter count. */
  waiterCount: number;
  /** Lifetime acquire / release / cancel counters synthesized client-side. */
  acquireCount: number;
  releaseCount: number;
  blockedAcquireCount: number;
  cancelledWaitCount: number;
  /** Highest blocked-waiter count observed in this session. */
  peakWaiterCount: number;
  /** Mean of every observed ``wait_seconds`` for blocked acquires. */
  meanWaitSeconds: number;
  maxWaitSeconds: number;
  /** Monotonic counter — bumped on every event applied to this record. */
  sequence: number;
}

// ── view-shape (projection-layer output) ────────────────────────────────

/** Per-semaphore card, ready for the panel + overlay. */
export interface SemaphoreContentionView {
  semaphoreId: string;
  semaphoreKind: SemaphoreKind;
  displayName: string;
  initialValue: number;
  boundValue: number | null;
  /** Permits in use right now (``initial − current``). Capped at
   *  ``initialValue`` for display safety. */
  permitsInUse: number;
  currentValue: number | null;
  waiterCount: number;
  peakWaiterCount: number;
  utilizationRatio: number;
  /** Visual severity — see :func:`deriveSeverity`. */
  severity: SemaphoreContentionSeverity;
  saturated: boolean;
  acquireCount: number;
  releaseCount: number;
  blockedAcquireCount: number;
  cancelledWaitCount: number;
  meanWaitSeconds: number;
  maxWaitSeconds: number;
  sequence: number;
}

// ── timeline marker view-shape ──────────────────────────────────────────

export type SemaphoreMarkerKind = "contention" | "saturation" | "wait-cancelled";

export interface SemaphoreContentionMarker {
  id: string;
  semaphoreId: string;
  kind: SemaphoreMarkerKind;
  severity: SemaphoreContentionSeverity;
  monotonicNs: number;
  label: string;
  detail?: string;
}
