/**
 * Wire + view models for the await dependency graph.
 *
 * Mirrors the backend types in
 * :mod:`asyncviz.runtime.events.models.gather`. Kept dependency-free
 * so the store / layout / renderer layers can import without React.
 *
 * Two collections drive the graph:
 *
 *   * ``nodes``   — tasks + gather invocations (each with a stable id).
 *   * ``edges``   — directed parent→child relationships (await edges
 *                   from a parent task to a gather it's awaiting, plus
 *                   fanout edges from a gather to each of its children).
 *
 * Topology is derived purely from the streamed event timeline — the
 * store keeps no per-node mutable state beyond what the events carry.
 */

// ── shared ──────────────────────────────────────────────────────────────

export type AwaitNodeKind = "task" | "gather";

export type AwaitNodeState =
  | "pending"
  | "running"
  | "completed"
  | "cancelled"
  | "failed";

export type AwaitEdgeKind =
  | "awaits"
  | "fanout"
  | "cancellation";

// ── wire-shape: gather event payloads ───────────────────────────────────

interface _GatherEventBase {
  event_type: string;
  gather_id: string;
  parent_task_id: string | null;
  child_count: number;
  snapshot: Record<string, unknown>;
}

export interface GatherCreatedPayload extends _GatherEventBase {
  event_type: "asyncio.gather.created";
  child_task_ids: string[];
  return_exceptions: boolean;
}

export interface GatherChildAttachedPayload extends _GatherEventBase {
  event_type: "asyncio.gather.child.attached";
  child_task_id: string;
  child_index: number;
}

export interface GatherWaitStartedPayload extends _GatherEventBase {
  event_type: "asyncio.gather.wait.started";
}

export interface GatherChildCompletedPayload extends _GatherEventBase {
  event_type: "asyncio.gather.child.completed";
  child_task_id: string;
  child_index: number;
  cancelled: boolean;
  failed: boolean;
  completed_count: number;
}

export interface GatherCompletedPayload extends _GatherEventBase {
  event_type: "asyncio.gather.completed";
  completed_count: number;
  cancelled_children: number;
  failed_children: number;
  duration_seconds: number | null;
}

export interface GatherCancelledPayload extends _GatherEventBase {
  event_type: "asyncio.gather.cancelled";
  completed_count: number;
  duration_seconds: number | null;
}

export interface GatherFailedPayload extends _GatherEventBase {
  event_type: "asyncio.gather.failed";
  completed_count: number;
  duration_seconds: number | null;
  exception_type: string | null;
}

export type AwaitGatherEventPayload =
  | GatherCreatedPayload
  | GatherChildAttachedPayload
  | GatherWaitStartedPayload
  | GatherChildCompletedPayload
  | GatherCompletedPayload
  | GatherCancelledPayload
  | GatherFailedPayload;

export const GATHER_EVENT_TYPES = [
  "asyncio.gather.created",
  "asyncio.gather.child.attached",
  "asyncio.gather.wait.started",
  "asyncio.gather.child.completed",
  "asyncio.gather.completed",
  "asyncio.gather.cancelled",
  "asyncio.gather.failed",
] as const;

export type GatherEventType = (typeof GATHER_EVENT_TYPES)[number];

// ── store-internal record types ─────────────────────────────────────────

export interface AwaitNodeRecord {
  id: string;
  kind: AwaitNodeKind;
  /** Human label — defaults to the id when no name is known. */
  label: string;
  state: AwaitNodeState;
  /** For gather nodes: the parent task awaiting it. */
  parentTaskId: string | null;
  /** For gather nodes: the count of children attached. */
  childCount: number;
  /** Number of children that have completed (gather nodes only). */
  completedCount: number;
  /** Number of children cancelled / failed. */
  cancelledCount: number;
  failedCount: number;
  /** Monotonic event count this node has absorbed — useful for stable
   *  ordering tie-breaks. */
  sequence: number;
  /** First-seen monotonic-ns. Drives stable layer ordering. */
  firstSeenNs: number;
  /** Last-seen monotonic-ns. Drives stale-node garbage collection. */
  lastSeenNs: number;
  /** Recorded exception class name (gather nodes that failed). */
  exceptionType: string | null;
  /** Duration in seconds (gather nodes after completion). */
  durationSeconds: number | null;
}

export interface AwaitEdgeRecord {
  id: string;
  kind: AwaitEdgeKind;
  fromId: string;
  toId: string;
  /** Optional positional index — populated for ``fanout`` edges from
   *  gather → child so renderers can preserve child ordering. */
  childIndex: number | null;
  /** ``true`` once the child reported done; lets the renderer style
   *  in-flight vs. settled edges differently. */
  completed: boolean;
  cancelled: boolean;
  failed: boolean;
  firstSeenNs: number;
  lastSeenNs: number;
}

// ── view-shape (projection-layer output) ────────────────────────────────

export interface AwaitNodeView {
  id: string;
  kind: AwaitNodeKind;
  label: string;
  state: AwaitNodeState;
  parentTaskId: string | null;
  childCount: number;
  completedCount: number;
  cancelledCount: number;
  failedCount: number;
  /** ``completedCount / childCount`` clamped to ``[0,1]``; ``0`` for
   *  task nodes. */
  progressRatio: number;
  exceptionType: string | null;
  durationSeconds: number | null;
}

export interface AwaitEdgeView {
  id: string;
  kind: AwaitEdgeKind;
  fromId: string;
  toId: string;
  completed: boolean;
  cancelled: boolean;
  failed: boolean;
  childIndex: number | null;
}
