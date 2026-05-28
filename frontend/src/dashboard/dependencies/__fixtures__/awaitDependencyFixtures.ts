import type {
  AwaitEdgeRecord,
  AwaitNodeRecord,
  GatherCancelledPayload,
  GatherChildAttachedPayload,
  GatherChildCompletedPayload,
  GatherCompletedPayload,
  GatherCreatedPayload,
  GatherFailedPayload,
  GatherWaitStartedPayload,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";

export function makeNode(
  overrides: Partial<AwaitNodeRecord> = {},
): AwaitNodeRecord {
  return {
    id: "t-1",
    kind: "task",
    label: "t-1",
    state: "running",
    parentTaskId: null,
    childCount: 0,
    completedCount: 0,
    cancelledCount: 0,
    failedCount: 0,
    sequence: 0,
    firstSeenNs: 0,
    lastSeenNs: 0,
    exceptionType: null,
    durationSeconds: null,
    ...overrides,
  };
}

export function makeEdge(
  overrides: Partial<AwaitEdgeRecord> = {},
): AwaitEdgeRecord {
  return {
    id: "fanout:g-1->t-1",
    kind: "fanout",
    fromId: "g-1",
    toId: "t-1",
    childIndex: 0,
    completed: false,
    cancelled: false,
    failed: false,
    firstSeenNs: 0,
    lastSeenNs: 0,
    ...overrides,
  };
}

export function makeGatherCreated(
  overrides: Partial<GatherCreatedPayload> = {},
): GatherCreatedPayload {
  return {
    event_type: "asyncio.gather.created",
    gather_id: "g-1",
    parent_task_id: "t-parent",
    child_count: 2,
    snapshot: {},
    child_task_ids: ["t-c1", "t-c2"],
    return_exceptions: false,
    ...overrides,
  };
}

export function makeChildAttached(
  overrides: Partial<GatherChildAttachedPayload> = {},
): GatherChildAttachedPayload {
  return {
    event_type: "asyncio.gather.child.attached",
    gather_id: "g-1",
    parent_task_id: "t-parent",
    child_count: 2,
    snapshot: {},
    child_task_id: "t-c1",
    child_index: 0,
    ...overrides,
  };
}

export function makeWaitStarted(
  overrides: Partial<GatherWaitStartedPayload> = {},
): GatherWaitStartedPayload {
  return {
    event_type: "asyncio.gather.wait.started",
    gather_id: "g-1",
    parent_task_id: "t-parent",
    child_count: 2,
    snapshot: {},
    ...overrides,
  };
}

export function makeChildCompleted(
  overrides: Partial<GatherChildCompletedPayload> = {},
): GatherChildCompletedPayload {
  return {
    event_type: "asyncio.gather.child.completed",
    gather_id: "g-1",
    parent_task_id: "t-parent",
    child_count: 2,
    snapshot: {},
    child_task_id: "t-c1",
    child_index: 0,
    cancelled: false,
    failed: false,
    completed_count: 1,
    ...overrides,
  };
}

export function makeGatherCompleted(
  overrides: Partial<GatherCompletedPayload> = {},
): GatherCompletedPayload {
  return {
    event_type: "asyncio.gather.completed",
    gather_id: "g-1",
    parent_task_id: "t-parent",
    child_count: 2,
    snapshot: {},
    completed_count: 2,
    cancelled_children: 0,
    failed_children: 0,
    duration_seconds: 0.05,
    ...overrides,
  };
}

export function makeGatherCancelled(
  overrides: Partial<GatherCancelledPayload> = {},
): GatherCancelledPayload {
  return {
    event_type: "asyncio.gather.cancelled",
    gather_id: "g-1",
    parent_task_id: "t-parent",
    child_count: 2,
    snapshot: {},
    completed_count: 1,
    duration_seconds: 0.02,
    ...overrides,
  };
}

export function makeGatherFailed(
  overrides: Partial<GatherFailedPayload> = {},
): GatherFailedPayload {
  return {
    event_type: "asyncio.gather.failed",
    gather_id: "g-1",
    parent_task_id: "t-parent",
    child_count: 2,
    snapshot: {},
    completed_count: 1,
    duration_seconds: 0.03,
    exception_type: "ValueError",
    ...overrides,
  };
}
