/**
 * Canonical row model for the live task table.
 *
 * The store keeps every task as a :class:`TaskSnapshot`. The table
 * works on a narrower projection — :class:`TaskRow` — that mixes
 * task lifecycle fields with timeline / warning / metrics annotations.
 * Projections live here so selectors and components stay UI-shaped,
 * and downstream consumers (sorting, filtering, virtualization,
 * accessibility) operate on one stable shape.
 *
 * Rows are *immutable*. Reconciliation is reference-based: two rows
 * with the same ``rowKey`` and ``signature`` represent the same row
 * with the same content. Memoized selectors rebuild rows only when
 * the underlying inputs change, so React reconciliation reuses keyed
 * DOM nodes between updates.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskLifecycleState,
  TaskSnapshot,
  WarningSeverity,
} from "@/types/runtime";
import { isFrameworkTask } from "@/dashboard/tasks/models/frameworkTasks";

/**
 * Canonical surface state for the table — wider than
 * :type:`TaskLifecycleState` because the table also distinguishes
 * "replaying" (a task that the snapshot rehydrated but that has not
 * yet been confirmed by deltas) and "orphaned" (a task whose parent
 * is no longer tracked).
 *
 * The mapping is deterministic so replays produce the same row state
 * every time.
 */
export type TaskRowStatus =
  | "pending"
  | "running"
  | "waiting"
  | "completed"
  | "cancelled"
  | "failed"
  | "replaying"
  | "orphaned";

/** Severity-prioritized warning summary attached to a row. */
export interface TaskRowWarningSummary {
  /** Total active warnings linked to this task. */
  count: number;
  /** Highest severity observed for any active warning. */
  highestSeverity: WarningSeverity | null;
}

/** Timeline indicator data — whether a task currently owns a span. */
export interface TaskRowTimelineSummary {
  /** ``true`` when there's an open run/wait segment for the task. */
  active: boolean;
  /** Segment count in this task's history (closed segments). */
  closedSegments: number;
  /** Most recent active segment, if any. */
  activeSegment: ActiveTimelineSegment | null;
}

/** Metrics overlay — derived counters for the row. */
export interface TaskRowMetricsSummary {
  /** Whether the row has been touched by a metrics delta recently. */
  recentlyTouched: boolean;
}

/**
 * One row in the live task table. The structure is intentionally
 * narrow: it carries everything cells need to render without forcing
 * cells to dereference :type:`TaskSnapshot` directly.
 */
export interface TaskRow {
  /** Stable identifier — used as React key. */
  rowKey: string;
  /** Source-of-truth task id (== rowKey today). */
  taskId: string;
  /** Backend lifecycle state. */
  lifecycleState: TaskLifecycleState;
  /** UI-facing state. May differ from ``lifecycleState`` (replaying / orphaned). */
  status: TaskRowStatus;
  /** Human-readable display label. */
  label: string;
  /** Coroutine name when available. */
  coroutineName: string | null;
  /** Task display name when available. */
  taskName: string | null;
  /** Parent task id (raw — may dangle if parent is no longer tracked). */
  parentTaskId: string | null;
  /** Whether the row references a parent we don't have. */
  isOrphaned: boolean;
  /** Topmost ancestor in the lineage chain. */
  rootTaskId: string | null;
  /** Lineage depth (0 for roots). */
  depth: number;
  /** Direct children counted by the tracker. */
  childCount: number;
  /** Backend ``created_at`` (wall seconds). */
  createdAt: number;
  /** Backend ``updated_at`` (wall seconds). */
  updatedAt: number;
  /** Backend ``completed_at`` (wall seconds, terminal only). */
  completedAt: number | null;
  /** Duration in seconds; ``null`` while still running. */
  durationSeconds: number | null;
  /** Whether this row is in a terminal state. */
  isTerminal: boolean;
  /** Replay hydrated this row but no delta has confirmed it yet. */
  isReplay: boolean;
  /** ``true`` when this row was created by framework infrastructure
   *  (Starlette/Uvicorn/FastAPI/AsyncViz internals) rather than the
   *  operator's own code. Hidden from the default Tasks view. */
  isFramework: boolean;
  /** Exception type / message — only set on failed rows. */
  exceptionType: string | null;
  exceptionMessage: string | null;
  /** Cancellation origin (e.g. ``"timeout"``) — only set on cancelled rows. */
  cancellationOrigin: string | null;
  /** Warning indicator computed from the warning index. */
  warnings: TaskRowWarningSummary;
  /** Timeline indicator computed from the timeline projection. */
  timeline: TaskRowTimelineSummary;
  /** Metrics indicator computed from the metrics delta map. */
  metrics: TaskRowMetricsSummary;
  /** Free-form annotations the inspector may want to surface. */
  tags: Record<string, string>;
  /**
   * Content signature — string concatenation of every field the table
   * displays. Memoized selectors compare signatures so duplicate
   * rows can collapse into the same React VDOM identity, and
   * pre/post-reconciliation diffs can be computed in O(1).
   */
  signature: string;
}

/** Severity-ordering helper — higher means more important. */
export const WARNING_SEVERITY_WEIGHT: Record<WarningSeverity, number> = {
  info: 1,
  warning: 2,
  error: 3,
  critical: 4,
};

const TERMINAL_STATES: ReadonlySet<TaskLifecycleState> = new Set([
  "completed",
  "cancelled",
  "failed",
]);

const STATUS_BY_LIFECYCLE: Record<TaskLifecycleState, TaskRowStatus> = {
  created: "pending",
  running: "running",
  waiting: "waiting",
  completed: "completed",
  cancelled: "cancelled",
  failed: "failed",
};

/** Pure: derive the UI status from a snapshot + signals. */
export function deriveTaskRowStatus(args: {
  lifecycleState: TaskLifecycleState;
  isOrphaned: boolean;
  isReplay: boolean;
}): TaskRowStatus {
  if (args.isOrphaned) return "orphaned";
  if (args.isReplay) return "replaying";
  return STATUS_BY_LIFECYCLE[args.lifecycleState];
}

/** Pure: best-severity reducer for a list of warnings linked to a row. */
export function summarizeRowWarnings(active: readonly ActiveWarning[]): TaskRowWarningSummary {
  if (active.length === 0) {
    return { count: 0, highestSeverity: null };
  }
  let count = 0;
  let highest: WarningSeverity | null = null;
  let highestWeight = 0;
  for (const w of active) {
    count += 1;
    const weight = WARNING_SEVERITY_WEIGHT[w.severity];
    if (weight > highestWeight) {
      highest = w.severity;
      highestWeight = weight;
    }
  }
  return { count, highestSeverity: highest };
}

/** Pure: shorten a possibly-null id to its display form. */
export function shortenTaskId(id: string): string {
  return id.length > 12 ? id.slice(0, 12) : id;
}

/** Pure: compute the label the row title cell will render. */
export function deriveRowLabel(task: TaskSnapshot): string {
  return task.task_name || task.coroutine_name || shortenTaskId(task.task_id);
}

/** Pure: row signature — folds everything visible into one string. */
export function rowSignature(row: Omit<TaskRow, "signature">): string {
  return [
    row.taskId,
    row.lifecycleState,
    row.status,
    row.label,
    row.coroutineName ?? "",
    row.taskName ?? "",
    row.parentTaskId ?? "",
    row.rootTaskId ?? "",
    String(row.depth),
    String(row.childCount),
    String(row.createdAt),
    String(row.updatedAt),
    row.completedAt === null ? "" : String(row.completedAt),
    row.durationSeconds === null ? "" : String(row.durationSeconds),
    row.isTerminal ? "1" : "0",
    row.isReplay ? "1" : "0",
    row.isOrphaned ? "1" : "0",
    row.isFramework ? "1" : "0",
    row.exceptionType ?? "",
    row.cancellationOrigin ?? "",
    String(row.warnings.count),
    row.warnings.highestSeverity ?? "",
    row.timeline.active ? "1" : "0",
    String(row.timeline.closedSegments),
    row.metrics.recentlyTouched ? "1" : "0",
  ].join("|");
}

export interface BuildRowInputs {
  task: TaskSnapshot;
  warningsForTask: readonly ActiveWarning[];
  activeSegment: ActiveTimelineSegment | null;
  closedSegmentCount: number;
  isReplay: boolean;
  parentExists: boolean;
  recentlyTouched: boolean;
}

/** Pure: build a single :type:`TaskRow` from the projection inputs. */
export function buildTaskRow(inputs: BuildRowInputs): TaskRow {
  const { task } = inputs;
  const isOrphaned = task.parent_task_id !== null && !inputs.parentExists;
  const status = deriveTaskRowStatus({
    lifecycleState: task.state,
    isOrphaned,
    isReplay: inputs.isReplay,
  });
  const warnings = summarizeRowWarnings(inputs.warningsForTask);
  const row: Omit<TaskRow, "signature"> = {
    rowKey: task.task_id,
    taskId: task.task_id,
    lifecycleState: task.state,
    status,
    label: deriveRowLabel(task),
    coroutineName: task.coroutine_name,
    taskName: task.task_name,
    parentTaskId: task.parent_task_id,
    isOrphaned,
    rootTaskId: task.root_task_id,
    depth: task.depth,
    childCount: task.child_count,
    createdAt: task.created_at,
    updatedAt: task.updated_at,
    completedAt: task.completed_at,
    durationSeconds: task.duration_seconds,
    isTerminal: TERMINAL_STATES.has(task.state),
    isReplay: inputs.isReplay,
    isFramework: isFrameworkTask({
      coroutineName: task.coroutine_name,
      taskName: task.task_name,
    }),
    exceptionType: task.exception_type,
    exceptionMessage: task.exception_message,
    cancellationOrigin: task.cancellation_origin,
    warnings,
    timeline: {
      active: inputs.activeSegment !== null,
      closedSegments: inputs.closedSegmentCount,
      activeSegment: inputs.activeSegment,
    },
    metrics: {
      recentlyTouched: inputs.recentlyTouched,
    },
    tags: task.tags ?? {},
  };
  return { ...row, signature: rowSignature(row) };
}

/** Pure: stable comparator used by the deterministic-order selector. */
export function compareRowsForStableOrder(a: TaskRow, b: TaskRow): number {
  if (a.createdAt !== b.createdAt) return a.createdAt - b.createdAt;
  return a.taskId.localeCompare(b.taskId);
}
