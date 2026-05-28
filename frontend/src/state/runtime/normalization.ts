/**
 * Snapshot normalization helpers.
 *
 * The backend ships a :class:`RuntimeSnapshot` envelope; the store
 * needs it in a normalized shape that can be folded into the existing
 * task-by-id map + per-state index. These functions are pure — call
 * them from a reducer, they don't touch the store directly.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  RuntimeSnapshot,
  TaskLifecycleState,
  TaskSnapshot,
  TimelineSegment,
  WarningSeverityCounts,
} from "@/types/runtime";
import type { NormalizedTimelineState, NormalizedWarningState } from "@/state/runtime/models";

/**
 * Build a ``Record<task_id, TaskSnapshot>`` + a per-state id index from
 * the snapshot's tasks array.
 */
export function normalizeTasks(tasks: TaskSnapshot[] | undefined): {
  tasksById: Record<string, TaskSnapshot>;
  taskIdsByState: Record<TaskLifecycleState, string[]>;
} {
  const tasksById: Record<string, TaskSnapshot> = {};
  const taskIdsByState: Record<TaskLifecycleState, string[]> = {
    created: [],
    running: [],
    waiting: [],
    completed: [],
    cancelled: [],
    failed: [],
  };
  if (tasks === undefined) {
    return { tasksById, taskIdsByState };
  }
  for (const task of tasks) {
    tasksById[task.task_id] = task;
    const bucket = taskIdsByState[task.state];
    if (bucket !== undefined) bucket.push(task.task_id);
  }
  return { tasksById, taskIdsByState };
}

/** Fold the snapshot's timeline projection into the normalized shape. */
export function normalizeTimeline(snapshot: RuntimeSnapshot): NormalizedTimelineState {
  const timeline = snapshot.timeline;
  if (timeline === null) {
    return {
      segmentsById: {},
      activeSegmentsByTaskId: {},
      segmentIdsByTaskId: {},
      lastSequence: 0,
    };
  }
  const segmentsById: Record<string, TimelineSegment> = {};
  const segmentIdsByTaskId: Record<string, string[]> = {};
  for (const track of timeline.tracks ?? []) {
    for (const span of track.spans ?? []) {
      for (const segment of span.segments ?? []) {
        segmentsById[segment.segment_id] = segment;
        const bucket = segmentIdsByTaskId[segment.task_id] ?? [];
        bucket.push(segment.segment_id);
        segmentIdsByTaskId[segment.task_id] = bucket;
      }
    }
  }
  // Sort each task's segment list by start time so iteration is stable.
  for (const taskId of Object.keys(segmentIdsByTaskId)) {
    segmentIdsByTaskId[taskId]!.sort((a, b) => {
      const segA = segmentsById[a]!;
      const segB = segmentsById[b]!;
      return segA.monotonic_start_ns - segB.monotonic_start_ns;
    });
  }
  const activeSegmentsByTaskId: Record<string, ActiveTimelineSegment> = {};
  for (const active of timeline.active_segments ?? []) {
    activeSegmentsByTaskId[active.task_id] = active;
  }
  return {
    segmentsById,
    activeSegmentsByTaskId,
    segmentIdsByTaskId,
    lastSequence: timeline.last_sequence ?? 0,
  };
}

const EMPTY_SEVERITY_COUNTS: WarningSeverityCounts = {
  info: 0,
  warning: 0,
  error: 0,
  critical: 0,
};

/** Fold the snapshot's warnings into the normalized warning state. */
export function normalizeWarnings(snapshot: RuntimeSnapshot): NormalizedWarningState {
  const warnings = snapshot.warnings;
  if (warnings === null) {
    return {
      warningsById: {},
      activeWarningIds: [],
      resolvedWarningIds: [],
      countsBySeverity: { ...EMPTY_SEVERITY_COUNTS },
    };
  }
  const warningsById: Record<string, ActiveWarning> = {};
  const activeWarningIds: string[] = [];
  const resolvedWarningIds: string[] = [];
  for (const warning of warnings.active ?? []) {
    warningsById[warning.warning_id] = warning;
    activeWarningIds.push(warning.warning_id);
  }
  for (const warning of warnings.resolved ?? []) {
    warningsById[warning.warning_id] = warning;
    resolvedWarningIds.push(warning.warning_id);
  }
  return {
    warningsById,
    activeWarningIds,
    resolvedWarningIds,
    countsBySeverity: {
      ...EMPTY_SEVERITY_COUNTS,
      ...warnings.counts_by_severity,
    },
  };
}
