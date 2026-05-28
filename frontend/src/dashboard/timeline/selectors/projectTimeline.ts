/**
 * Pure projection: runtime store timeline state → renderer dataset.
 *
 * The store keeps timeline segments under a normalized index keyed by
 * task id; the renderer needs flat arrays of rows + segments with
 * world-space coordinates (seconds, row index).
 *
 * The projection is pure so it's testable without React / Zustand
 * and reusable on a worker thread later.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskSnapshot,
  TimelineSegment,
} from "@/types/runtime";
import type {
  TimelineRenderSegment,
  TimelineRow,
  TimelineRowState,
  TimelineRowWarningSeverity,
  TimelineSegmentLifecycleState,
} from "@/dashboard/timeline/rendering/TimelineLayer";

export interface TimelineProjectionInputs {
  tasksById: Record<string, TaskSnapshot>;
  segmentsById: Record<string, TimelineSegment>;
  segmentIdsByTaskId: Record<string, string[]>;
  activeSegmentsByTaskId: Record<string, ActiveTimelineSegment>;
  /** Currently-active warnings — used to decorate rows. Optional so
   *  callers that don't care can omit it. */
  activeWarnings?: readonly ActiveWarning[];
}

export interface TimelineProjection {
  rows: readonly TimelineRow[];
  segments: readonly TimelineRenderSegment[];
  /** Smallest start time across the projection — used to anchor the camera. */
  minStartSeconds: number;
  /** Largest end time across the projection — used to bound the camera. */
  maxEndSeconds: number;
}

export const EMPTY_PROJECTION: TimelineProjection = {
  rows: [],
  segments: [],
  minStartSeconds: 0,
  maxEndSeconds: 0,
};

function nsToSeconds(value: number): number {
  return value / 1e9;
}

function compareTasks(a: TaskSnapshot, b: TaskSnapshot): number {
  if (a.created_at !== b.created_at) return a.created_at - b.created_at;
  return a.task_id.localeCompare(b.task_id);
}

function deriveRowLabel(task: TaskSnapshot): string {
  return task.task_name || task.coroutine_name || task.task_id;
}

function normalizeRowState(value: string | undefined): TimelineRowState {
  switch (value) {
    case "created":
    case "running":
    case "waiting":
    case "completed":
    case "cancelled":
    case "failed":
      return value;
    default:
      return "unknown";
  }
}

const SEVERITY_RANK: Record<TimelineRowWarningSeverity, number> = {
  info: 1,
  warning: 2,
  error: 3,
  critical: 4,
};

function buildRowWarningIndex(
  warnings: readonly ActiveWarning[] | undefined,
): Map<string, { severity: TimelineRowWarningSeverity; count: number }> {
  const out = new Map<string, { severity: TimelineRowWarningSeverity; count: number }>();
  if (!warnings) return out;
  for (const warning of warnings) {
    if (warning.resolved || warning.expired) continue;
    for (const taskId of warning.related_task_ids) {
      const current = out.get(taskId);
      if (current === undefined) {
        out.set(taskId, { severity: warning.severity, count: 1 });
        continue;
      }
      current.count += 1;
      if (SEVERITY_RANK[warning.severity] > SEVERITY_RANK[current.severity]) {
        current.severity = warning.severity;
      }
    }
  }
  return out;
}

function intentForSegment(segment: TimelineSegment): TimelineRenderSegment["intent"] {
  if (segment.segment_type === "run") return "run";
  if (segment.segment_type === "wait") return "wait";
  return "default";
}

function lifecycleForSegment(
  segment: TimelineSegment,
  taskState: TimelineRowState,
): TimelineSegmentLifecycleState {
  // Closed segments take their concrete type when the task is not
  // already terminal; terminal task states win because finalization
  // is the higher-fidelity signal.
  if (taskState === "cancelled") return "cancelled";
  if (taskState === "failed") return "failed";
  if (taskState === "completed") return "completed";
  if (segment.segment_type === "wait") return "waiting";
  if (segment.segment_type === "run") return "running";
  return "unknown";
}

function lifecycleForActive(
  segment: ActiveTimelineSegment,
): TimelineSegmentLifecycleState {
  return segment.segment_type === "wait" ? "waiting" : "running";
}

export function projectTimeline(inputs: TimelineProjectionInputs): TimelineProjection {
  const tasks = Object.values(inputs.tasksById).slice().sort(compareTasks);
  if (tasks.length === 0) return EMPTY_PROJECTION;

  const warningIndex = buildRowWarningIndex(inputs.activeWarnings);
  const rowStateByTask = new Map<string, TimelineRowState>();
  const rows: TimelineRow[] = tasks.map((task, index) => {
    const warningTally = warningIndex.get(task.task_id);
    const state = normalizeRowState(task.state);
    rowStateByTask.set(task.task_id, state);
    return {
      rowIndex: index,
      taskId: task.task_id,
      label: deriveRowLabel(task),
      coroutineName: task.coroutine_name ?? null,
      state,
      parentTaskId: task.parent_task_id ?? null,
      depth: Number.isFinite(task.depth) ? task.depth : 0,
      childCount: Number.isFinite(task.child_count) ? task.child_count : 0,
      warningSeverity: warningTally?.severity ?? null,
      warningCount: warningTally?.count ?? 0,
      replay: null,
      createdAtMonotonicNs:
        Number.isFinite(task.created_at) && task.created_at > 0
          ? Math.round(task.created_at * 1e9)
          : 0,
    };
  });
  const rowIndexByTask = new Map<string, number>();
  const depthByTask = new Map<string, number>();
  const parentByTask = new Map<string, string | null>();
  tasks.forEach((task, index) => {
    rowIndexByTask.set(task.task_id, index);
    depthByTask.set(task.task_id, Number.isFinite(task.depth) ? task.depth : 0);
    parentByTask.set(task.task_id, task.parent_task_id ?? null);
  });

  const segments: TimelineRenderSegment[] = [];
  let minStart = Number.POSITIVE_INFINITY;
  let maxEnd = Number.NEGATIVE_INFINITY;

  for (const [taskId, segmentIds] of Object.entries(inputs.segmentIdsByTaskId)) {
    const rowIndex = rowIndexByTask.get(taskId);
    if (rowIndex === undefined) continue;
    const taskState = rowStateByTask.get(taskId) ?? "unknown";
    const warningTally = warningIndex.get(taskId);
    for (const segmentId of segmentIds) {
      const segment = inputs.segmentsById[segmentId];
      if (segment === undefined) continue;
      const startSeconds = nsToSeconds(segment.monotonic_start_ns);
      const endSeconds = nsToSeconds(segment.monotonic_end_ns);
      if (startSeconds < minStart) minStart = startSeconds;
      if (endSeconds > maxEnd) maxEnd = endSeconds;
      segments.push({
        segmentId,
        rowIndex,
        taskId,
        startSeconds,
        endSeconds,
        intent: intentForSegment(segment),
        isActive: false,
        lifecycleState: lifecycleForSegment(segment, taskState),
        sequenceStart: segment.sequence_start,
        sequenceEnd: segment.sequence_end,
        durationNs: segment.duration_ns,
        warningSeverity: warningTally?.severity ?? null,
        replay: null,
        parentTaskId: parentByTask.get(taskId) ?? null,
        depth: depthByTask.get(taskId) ?? 0,
      });
    }
  }

  for (const [taskId, active] of Object.entries(inputs.activeSegmentsByTaskId)) {
    const rowIndex = rowIndexByTask.get(taskId);
    if (rowIndex === undefined) continue;
    const warningTally = warningIndex.get(taskId);
    const startSeconds = nsToSeconds(active.monotonic_start_ns);
    // Active segments don't have an end yet — render them to the
    // running edge of the projection (or 1s ahead if no other data).
    const endSeconds = Math.max(maxEnd, startSeconds + 1);
    if (startSeconds < minStart) minStart = startSeconds;
    if (endSeconds > maxEnd) maxEnd = endSeconds;
    segments.push({
      segmentId: active.segment_id,
      rowIndex,
      taskId,
      startSeconds,
      endSeconds,
      intent: active.segment_type === "wait" ? "wait" : "run",
      isActive: true,
      lifecycleState: lifecycleForActive(active),
      sequenceStart: active.sequence_start,
      sequenceEnd: null,
      durationNs: undefined,
      warningSeverity: warningTally?.severity ?? null,
      replay: null,
      parentTaskId: parentByTask.get(taskId) ?? null,
      depth: depthByTask.get(taskId) ?? 0,
    });
  }

  if (!Number.isFinite(minStart)) minStart = 0;
  if (!Number.isFinite(maxEnd)) maxEnd = Math.max(1, minStart + 1);

  return {
    rows,
    segments,
    minStartSeconds: minStart,
    maxEndSeconds: maxEnd,
  };
}
