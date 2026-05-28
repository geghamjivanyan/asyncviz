/**
 * Pure projection helpers that build a :type:`TaskInspection` from
 * the raw runtime-store slices.
 *
 * Keeping the projection pure makes it cheap to memoize at the React
 * boundary + easy to test without mounting components.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskSnapshot,
  TaskTransitionRecord,
  TimelineSegment,
} from "@/types/runtime";
import {
  EMPTY_TASK_INSPECTION,
  type InspectorLifecycleState,
  type InspectorLifecycleSummary,
  type InspectorMetricsSummary,
  type InspectorRelationships,
  type InspectorReplaySummary,
  type InspectorTimelineSummary,
  type InspectorWarningsSummary,
  type TaskInspection,
} from "@/dashboard/inspector/models/TaskInspectionModels";

const RECENT_SEGMENT_LIMIT = 16;

const SEVERITY_RANK: Record<ActiveWarning["severity"], number> = {
  info: 1,
  warning: 2,
  error: 3,
  critical: 4,
};

function nsToSeconds(value: number): number {
  return value / 1e9;
}

function isTerminal(state: string | undefined): boolean {
  return state === "completed" || state === "cancelled" || state === "failed";
}

function normalizeState(value: string | undefined): InspectorLifecycleState {
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

/** Pure: build the lifecycle slice. */
export function buildLifecycleSummary(
  task: TaskSnapshot | null,
  transitions: readonly TaskTransitionRecord[] = [],
  active: boolean = false,
): InspectorLifecycleSummary {
  if (task === null) {
    return EMPTY_TASK_INSPECTION.lifecycle;
  }
  return {
    state: normalizeState(task.state),
    createdAtSeconds: Number.isFinite(task.created_at) ? task.created_at : null,
    completedAtSeconds:
      task.completed_at !== null && Number.isFinite(task.completed_at)
        ? task.completed_at
        : null,
    durationSeconds:
      task.duration_seconds !== null && Number.isFinite(task.duration_seconds)
        ? task.duration_seconds
        : null,
    terminal: isTerminal(task.state),
    active,
    transitions,
  };
}

/** Pure: build the timeline slice. */
export function buildTimelineSummary(args: {
  segments: readonly TimelineSegment[];
  activeSegment: ActiveTimelineSegment | null;
}): InspectorTimelineSummary {
  const { segments, activeSegment } = args;
  let runSegmentCount = 0;
  let waitSegmentCount = 0;
  let totalRunNs = 0;
  let totalWaitNs = 0;
  let firstStartNs = Number.POSITIVE_INFINITY;
  let lastEndNs = Number.NEGATIVE_INFINITY;
  for (const segment of segments) {
    if (segment.segment_type === "run") {
      runSegmentCount += 1;
      totalRunNs += segment.duration_ns;
    } else if (segment.segment_type === "wait") {
      waitSegmentCount += 1;
      totalWaitNs += segment.duration_ns;
    }
    if (segment.monotonic_start_ns < firstStartNs) firstStartNs = segment.monotonic_start_ns;
    if (segment.monotonic_end_ns > lastEndNs) lastEndNs = segment.monotonic_end_ns;
  }
  const recent = segments.slice(-RECENT_SEGMENT_LIMIT);
  return {
    segmentCount: segments.length,
    runSegmentCount,
    waitSegmentCount,
    totalRunSeconds: nsToSeconds(totalRunNs),
    totalWaitSeconds: nsToSeconds(totalWaitNs),
    firstSegmentStartSeconds: Number.isFinite(firstStartNs) ? nsToSeconds(firstStartNs) : null,
    lastSegmentEndSeconds: Number.isFinite(lastEndNs) ? nsToSeconds(lastEndNs) : null,
    activeSegment,
    recentSegments: recent,
  };
}

/** Pure: build the relationships slice. */
export function buildRelationships(
  task: TaskSnapshot | null,
  childTaskIds: readonly string[],
  siblingCount: number,
): InspectorRelationships {
  if (task === null) {
    return EMPTY_TASK_INSPECTION.relationships;
  }
  return {
    parentTaskId: task.parent_task_id ?? null,
    rootTaskId: task.root_task_id ?? task.task_id,
    depth: Number.isFinite(task.depth) ? task.depth : 0,
    ancestorChain: task.ancestor_chain ?? [],
    childTaskIds,
    siblingCount,
  };
}

/** Pure: build the warnings slice. */
export function buildWarningsSummary(
  active: readonly ActiveWarning[],
): InspectorWarningsSummary {
  let highest: ActiveWarning["severity"] | null = null;
  for (const warning of active) {
    if (warning.resolved || warning.expired) continue;
    if (highest === null || SEVERITY_RANK[warning.severity] > SEVERITY_RANK[highest]) {
      highest = warning.severity;
    }
  }
  return {
    active,
    highestSeverity: highest,
    count: active.length,
  };
}

/** Pure: build the metrics slice. */
export function buildMetricsSummary(args: {
  timeline: InspectorTimelineSummary;
  lifecycle: InspectorLifecycleSummary;
  coroutineThroughputPerSecond?: number | null;
}): InspectorMetricsSummary {
  const { timeline, lifecycle, coroutineThroughputPerSecond } = args;
  const liveSeconds =
    lifecycle.durationSeconds !== null
      ? lifecycle.durationSeconds
      : timeline.lastSegmentEndSeconds !== null && timeline.firstSegmentStartSeconds !== null
        ? Math.max(0, timeline.lastSegmentEndSeconds - timeline.firstSegmentStartSeconds)
        : null;
  const observed = timeline.totalRunSeconds + timeline.totalWaitSeconds;
  const denominator =
    liveSeconds !== null && liveSeconds > 0
      ? liveSeconds
      : observed > 0
        ? observed
        : null;
  const runRatio =
    denominator !== null && denominator > 0 ? timeline.totalRunSeconds / denominator : null;
  const waitRatio =
    denominator !== null && denominator > 0 ? timeline.totalWaitSeconds / denominator : null;
  let maxDurationNs = 0;
  for (const segment of timeline.recentSegments) {
    if (segment.duration_ns > maxDurationNs) maxDurationNs = segment.duration_ns;
  }
  const averageSegmentSeconds =
    timeline.segmentCount > 0
      ? (timeline.totalRunSeconds + timeline.totalWaitSeconds) / timeline.segmentCount
      : null;
  return {
    runRatio,
    waitRatio,
    averageSegmentSeconds,
    maxSegmentSeconds: maxDurationNs > 0 ? maxDurationNs / 1e9 : null,
    coroutineThroughputPerSecond: coroutineThroughputPerSecond ?? null,
  };
}

/** Pure: build the replay slice. */
export function buildReplaySummary(args: {
  oldestRetainedSequence: number | null;
  newestRetainedSequence: number | null;
  windowHit: boolean;
  lastSequence: number;
}): InspectorReplaySummary {
  return {
    oldestRetainedSequence: args.oldestRetainedSequence,
    newestRetainedSequence: args.newestRetainedSequence,
    windowHit: args.windowHit,
    lastSequence: args.lastSequence,
  };
}

export interface BuildInspectionArgs {
  task: TaskSnapshot | null;
  transitions?: readonly TaskTransitionRecord[];
  segments?: readonly TimelineSegment[];
  activeSegment?: ActiveTimelineSegment | null;
  activeWarnings?: readonly ActiveWarning[];
  childTaskIds?: readonly string[];
  siblingCount?: number;
  coroutineThroughputPerSecond?: number | null;
  replay?: {
    oldestRetainedSequence: number | null;
    newestRetainedSequence: number | null;
    windowHit: boolean;
    lastSequence: number;
  };
  generation?: number;
}

/** Pure: assemble a complete :type:`TaskInspection`. */
export function buildTaskInspection(args: BuildInspectionArgs): TaskInspection {
  if (args.task === null) {
    return {
      ...EMPTY_TASK_INSPECTION,
      generation: args.generation ?? 0,
    };
  }
  const activeSegment = args.activeSegment ?? null;
  const lifecycle = buildLifecycleSummary(
    args.task,
    args.transitions ?? [],
    activeSegment !== null,
  );
  const timeline = buildTimelineSummary({
    segments: args.segments ?? [],
    activeSegment,
  });
  const relationships = buildRelationships(
    args.task,
    args.childTaskIds ?? [],
    args.siblingCount ?? 0,
  );
  const warnings = buildWarningsSummary(args.activeWarnings ?? []);
  const metrics = buildMetricsSummary({
    timeline,
    lifecycle,
    coroutineThroughputPerSecond: args.coroutineThroughputPerSecond ?? null,
  });
  const replay = args.replay
    ? buildReplaySummary(args.replay)
    : EMPTY_TASK_INSPECTION.replay;
  return {
    task: args.task,
    state: lifecycle.state,
    lifecycle,
    timeline,
    relationships,
    warnings,
    metrics,
    replay,
    generation: args.generation ?? 0,
  };
}
