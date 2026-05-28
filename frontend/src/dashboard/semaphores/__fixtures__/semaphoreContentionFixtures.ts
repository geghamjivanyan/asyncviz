import type {
  SemaphoreAcquireStartedPayload,
  SemaphoreAcquiredPayload,
  SemaphoreContentionDetectedPayload,
  SemaphoreCreatedPayload,
  SemaphoreHydrationResponse,
  SemaphoreIdentityRecord,
  SemaphoreMetricsRecord,
  SemaphoreRecord,
  SemaphoreReleasedPayload,
  SemaphoreSnapshotRecord,
  SemaphoreWaitCancelledPayload,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export function makeIdentity(
  overrides: Partial<SemaphoreIdentityRecord> = {},
): SemaphoreIdentityRecord {
  return {
    semaphore_id: "s-1",
    semaphore_kind: "Semaphore",
    initial_value: 4,
    bound_value: null,
    creator_task_id: null,
    name: null,
    ...overrides,
  };
}

export function makeRecord(overrides: Partial<SemaphoreRecord> = {}): SemaphoreRecord {
  return {
    semaphoreId: "s-1",
    semaphoreKind: "Semaphore",
    initialValue: 4,
    boundValue: null,
    creatorTaskId: null,
    name: null,
    currentValue: 4,
    waiterCount: 0,
    acquireCount: 0,
    releaseCount: 0,
    blockedAcquireCount: 0,
    cancelledWaitCount: 0,
    peakWaiterCount: 0,
    meanWaitSeconds: 0,
    maxWaitSeconds: 0,
    sequence: 0,
    ...overrides,
  };
}

export function makeSnapshot(
  overrides: Partial<SemaphoreSnapshotRecord> = {},
): SemaphoreSnapshotRecord {
  return {
    current_value: 4,
    waiter_count: 0,
    initial_value: 4,
    bound_value: null,
    ...overrides,
  };
}

export function makeMetrics(
  overrides: Partial<SemaphoreMetricsRecord> = {},
): SemaphoreMetricsRecord {
  return {
    semaphores_registered: 0,
    semaphores_finalized: 0,
    events_emitted: 0,
    events_dropped: 0,
    acquire_events: 0,
    release_events: 0,
    cancelled_waits: 0,
    contention_detections: 0,
    blocked_acquires: 0,
    recursion_skips: 0,
    ...overrides,
  };
}

export function makeHydration(
  overrides: Partial<SemaphoreHydrationResponse> = {},
): SemaphoreHydrationResponse {
  return {
    registry_size: 0,
    registry_finalized: 0,
    metrics: makeMetrics(),
    trace_enabled: false,
    trace_count: 0,
    semaphores: [],
    ...overrides,
  };
}

export function makeCreated(
  overrides: Partial<SemaphoreCreatedPayload> = {},
): SemaphoreCreatedPayload {
  return {
    event_type: "asyncio.semaphore.created",
    semaphore_id: "s-1",
    semaphore_kind: "Semaphore",
    initial_value: 4,
    bound_value: null,
    task_id: null,
    snapshot: makeSnapshot(),
    creator_task_id: null,
    name: null,
    ...overrides,
  };
}

export function makeAcquireStarted(
  overrides: Partial<SemaphoreAcquireStartedPayload> = {},
): SemaphoreAcquireStartedPayload {
  return {
    event_type: "asyncio.semaphore.acquire.started",
    semaphore_id: "s-1",
    semaphore_kind: "Semaphore",
    initial_value: 4,
    bound_value: null,
    task_id: null,
    snapshot: makeSnapshot(),
    will_block: false,
    ...overrides,
  };
}

export function makeAcquired(
  overrides: Partial<SemaphoreAcquiredPayload> = {},
): SemaphoreAcquiredPayload {
  return {
    event_type: "asyncio.semaphore.acquired",
    semaphore_id: "s-1",
    semaphore_kind: "Semaphore",
    initial_value: 4,
    bound_value: null,
    task_id: null,
    snapshot: makeSnapshot({ current_value: 3 }),
    blocked: false,
    wait_seconds: null,
    ...overrides,
  };
}

export function makeReleased(
  overrides: Partial<SemaphoreReleasedPayload> = {},
): SemaphoreReleasedPayload {
  return {
    event_type: "asyncio.semaphore.released",
    semaphore_id: "s-1",
    semaphore_kind: "Semaphore",
    initial_value: 4,
    bound_value: null,
    task_id: null,
    snapshot: makeSnapshot({ current_value: 4 }),
    ...overrides,
  };
}

export function makeContention(
  overrides: Partial<SemaphoreContentionDetectedPayload> = {},
): SemaphoreContentionDetectedPayload {
  return {
    event_type: "asyncio.semaphore.contention.detected",
    semaphore_id: "s-1",
    semaphore_kind: "Semaphore",
    initial_value: 4,
    bound_value: null,
    task_id: null,
    snapshot: makeSnapshot({ current_value: 0, waiter_count: 1 }),
    waiter_count: 1,
    current_value: 0,
    ...overrides,
  };
}

export function makeCancelled(
  overrides: Partial<SemaphoreWaitCancelledPayload> = {},
): SemaphoreWaitCancelledPayload {
  return {
    event_type: "asyncio.semaphore.wait.cancelled",
    semaphore_id: "s-1",
    semaphore_kind: "Semaphore",
    initial_value: 4,
    bound_value: null,
    task_id: null,
    snapshot: makeSnapshot({ current_value: 0, waiter_count: 0 }),
    wait_seconds: 0.5,
    ...overrides,
  };
}
