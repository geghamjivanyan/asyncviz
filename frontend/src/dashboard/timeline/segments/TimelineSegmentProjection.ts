/**
 * Pure projection: runtime store timeline state → canonical
 * :type:`TimelineSegmentProjection`.
 *
 * The function is intentionally:
 *
 *   * pure — no React, no Zustand,
 *   * deterministic — same input → identical output (including
 *     ordering),
 *   * cheap — one pass over closed segments + one pass over actives,
 *   * replay-safe — every projection captures a ``sequence`` cursor.
 *
 * The projection re-uses the existing :func:`projectTimeline` shape
 * for the segment array, then re-builds index structures sorted by
 * ``(rowIndex, startSeconds, segmentId)`` so downstream code can scan
 * row-major without resorting per frame.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskSnapshot,
  TimelineSegment,
  WarningSeverity,
} from "@/types/runtime";
import type {
  TimelineRowWarningSeverity,
  TimelineSegmentLifecycleState,
  TimelineSegmentReplayMark,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import {
  EMPTY_TIMELINE_SEGMENT_PROJECTION,
  type TimelineSegmentProjection,
  type TimelineSegmentProjectionEntry,
} from "@/dashboard/timeline/segments/models/TimelineSegmentModels";

export interface TimelineSegmentProjectionInputs {
  tasksById: Readonly<Record<string, TaskSnapshot>>;
  segmentsById: Readonly<Record<string, TimelineSegment>>;
  segmentIdsByTaskId: Readonly<Record<string, readonly string[]>>;
  activeSegmentsByTaskId: Readonly<Record<string, ActiveTimelineSegment>>;
  activeWarnings?: readonly ActiveWarning[];
  /** Replay cursor — drives the per-segment replay marks. */
  replay?: {
    sequence: number | null;
    focusedSegmentId?: string | null;
    focusedTaskId?: string | null;
  } | null;
  /** Sequence cursor of the source data. */
  sequence?: number;
}

const SEVERITY_RANK: Record<TimelineRowWarningSeverity, number> = {
  info: 1,
  warning: 2,
  error: 3,
  critical: 4,
};

function nsToSeconds(value: number): number {
  return value / 1e9;
}

function compareTasks(a: TaskSnapshot, b: TaskSnapshot): number {
  if (a.created_at !== b.created_at) return a.created_at - b.created_at;
  return a.task_id.localeCompare(b.task_id);
}

function buildWarningSeverityIndex(
  warnings: readonly ActiveWarning[] | undefined,
): Map<string, TimelineRowWarningSeverity> {
  const out = new Map<string, TimelineRowWarningSeverity>();
  if (!warnings) return out;
  for (const warning of warnings) {
    if (warning.resolved || warning.expired) continue;
    const severity: WarningSeverity = warning.severity;
    for (const taskId of warning.related_task_ids) {
      const current = out.get(taskId);
      if (current === undefined || SEVERITY_RANK[severity] > SEVERITY_RANK[current]) {
        out.set(taskId, severity);
      }
    }
  }
  return out;
}

function lifecycleForClosed(
  segment: TimelineSegment,
  terminalRowState: TimelineSegmentLifecycleState | null,
): TimelineSegmentLifecycleState {
  if (terminalRowState !== null) return terminalRowState;
  if (segment.segment_type === "wait") return "waiting";
  if (segment.segment_type === "run") return "running";
  return "unknown";
}

function lifecycleForActive(segment: ActiveTimelineSegment): TimelineSegmentLifecycleState {
  return segment.segment_type === "wait" ? "waiting" : "running";
}

function terminalRowState(task: TaskSnapshot): TimelineSegmentLifecycleState | null {
  switch (task.state) {
    case "completed":
      return "completed";
    case "cancelled":
      return "cancelled";
    case "failed":
      return "failed";
    default:
      return null;
  }
}

function buildReplayMark(
  segmentId: string,
  taskId: string,
  isActive: boolean,
  replay: TimelineSegmentProjectionInputs["replay"],
): TimelineSegmentReplayMark | null {
  if (!replay) return null;
  const focusedSegment = replay.focusedSegmentId === segmentId;
  const focusedTask = replay.focusedTaskId === taskId;
  if (!focusedSegment && !focusedTask) return null;
  return {
    sequence: replay.sequence,
    focused: focusedSegment,
    finalizedBeforeCursor: !isActive,
  };
}

function compareEntries(
  a: TimelineSegmentProjectionEntry,
  b: TimelineSegmentProjectionEntry,
): number {
  if (a.rowIndex !== b.rowIndex) return a.rowIndex - b.rowIndex;
  if (a.startSeconds !== b.startSeconds) return a.startSeconds - b.startSeconds;
  if (a.endSeconds !== b.endSeconds) return a.endSeconds - b.endSeconds;
  return a.segmentId.localeCompare(b.segmentId);
}

/** Pure: build the canonical segment projection. */
export function projectTimelineSegments(
  inputs: TimelineSegmentProjectionInputs,
): TimelineSegmentProjection {
  const taskList = Object.values(inputs.tasksById).slice().sort(compareTasks);
  if (taskList.length === 0) return EMPTY_TIMELINE_SEGMENT_PROJECTION;

  const rowIndexByTask = new Map<string, number>();
  const depthByTask = new Map<string, number>();
  const parentByTask = new Map<string, string | null>();
  const terminalByTask = new Map<string, TimelineSegmentLifecycleState | null>();
  for (let i = 0; i < taskList.length; i += 1) {
    const task = taskList[i];
    rowIndexByTask.set(task.task_id, i);
    depthByTask.set(task.task_id, Number.isFinite(task.depth) ? task.depth : 0);
    parentByTask.set(task.task_id, task.parent_task_id ?? null);
    terminalByTask.set(task.task_id, terminalRowState(task));
  }

  const severityByTask = buildWarningSeverityIndex(inputs.activeWarnings);
  const entries: TimelineSegmentProjectionEntry[] = [];
  let hasActiveSegments = false;

  for (const [taskId, segmentIds] of Object.entries(inputs.segmentIdsByTaskId)) {
    const rowIndex = rowIndexByTask.get(taskId);
    if (rowIndex === undefined) continue;
    const terminal = terminalByTask.get(taskId) ?? null;
    const severity = severityByTask.get(taskId) ?? null;
    const depth = depthByTask.get(taskId) ?? 0;
    const parent = parentByTask.get(taskId) ?? null;
    for (const segmentId of segmentIds) {
      const segment = inputs.segmentsById[segmentId];
      if (segment === undefined) continue;
      const startSeconds = nsToSeconds(segment.monotonic_start_ns);
      const endSeconds = nsToSeconds(segment.monotonic_end_ns);
      const durationSeconds = Math.max(0, endSeconds - startSeconds);
      const lifecycleState = lifecycleForClosed(segment, terminal);
      const replay = buildReplayMark(segmentId, taskId, false, inputs.replay ?? null);
      entries.push({
        segmentId,
        entryId: segmentId,
        rowIndex,
        taskId,
        startSeconds,
        endSeconds,
        intent: segment.segment_type === "run" ? "run" : "wait",
        isActive: false,
        lifecycleState,
        sequenceStart: segment.sequence_start,
        sequenceEnd: segment.sequence_end,
        durationNs: segment.duration_ns,
        warningSeverity: severity,
        replay,
        parentTaskId: parent,
        depth,
        durationSeconds,
      });
    }
  }

  for (const [taskId, active] of Object.entries(inputs.activeSegmentsByTaskId)) {
    const rowIndex = rowIndexByTask.get(taskId);
    if (rowIndex === undefined) continue;
    const severity = severityByTask.get(taskId) ?? null;
    const depth = depthByTask.get(taskId) ?? 0;
    const parent = parentByTask.get(taskId) ?? null;
    const startSeconds = nsToSeconds(active.monotonic_start_ns);
    // Active segments don't have an end on the wire; consumers render
    // them up to the camera's right edge. We park them with the start
    // as the end so geometry remains valid; the renderer extends to
    // ``cameraEnd`` at draw time.
    const endSeconds = startSeconds;
    const lifecycleState = lifecycleForActive(active);
    const replay = buildReplayMark(active.segment_id, taskId, true, inputs.replay ?? null);
    entries.push({
      segmentId: active.segment_id,
      entryId: active.segment_id,
      rowIndex,
      taskId,
      startSeconds,
      endSeconds,
      intent: active.segment_type === "wait" ? "wait" : "run",
      isActive: true,
      lifecycleState,
      sequenceStart: active.sequence_start,
      sequenceEnd: null,
      warningSeverity: severity,
      replay,
      parentTaskId: parent,
      depth,
      durationSeconds: 0,
    });
    hasActiveSegments = true;
  }

  entries.sort(compareEntries);

  const indexBySegmentId = new Map<string, number>();
  const indicesByTaskId = new Map<string, number[]>();
  for (let i = 0; i < entries.length; i += 1) {
    const entry = entries[i];
    indexBySegmentId.set(entry.segmentId, i);
    const bucket = indicesByTaskId.get(entry.taskId);
    if (bucket === undefined) {
      indicesByTaskId.set(entry.taskId, [i]);
    } else {
      bucket.push(i);
    }
  }

  return {
    segments: entries,
    indexBySegmentId,
    indicesByTaskId: indicesByTaskId as ReadonlyMap<string, readonly number[]>,
    sequence: inputs.sequence ?? 0,
    totalSegments: entries.length,
    hasActiveSegments,
  };
}
