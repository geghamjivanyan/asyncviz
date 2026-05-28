/**
 * Test builders for lifecycle segments + active segments. Mirrors the
 * backend wire shape so projection logic exercises the real path.
 */

import type {
  ActiveTimelineSegment,
  TimelineSegment,
} from "@/types/runtime";
import type {
  TimelineRenderSegment,
  TimelineSegmentLifecycleState,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import type { TimelineSegmentProjectionEntry } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";
import { normalizeSegment } from "@/dashboard/timeline/segments/utils/normalizeSegment";

export function makeWireSegment(
  segmentId: string,
  taskId: string,
  startNs: number,
  endNs: number,
  overrides: Partial<TimelineSegment> = {},
): TimelineSegment {
  return {
    task_id: taskId,
    segment_id: segmentId,
    segment_type: "run",
    sequence_start: 1,
    sequence_end: 2,
    monotonic_start_ns: startNs,
    monotonic_end_ns: endNs,
    duration_ns: endNs - startNs,
    wall_start: 0,
    wall_end: 0,
    state: "running",
    parent_task_id: null,
    coroutine_name: null,
    task_name: null,
    metadata: {},
    ...overrides,
  };
}

export function makeActiveWireSegment(
  segmentId: string,
  taskId: string,
  startNs: number,
  overrides: Partial<ActiveTimelineSegment> = {},
): ActiveTimelineSegment {
  return {
    task_id: taskId,
    segment_id: segmentId,
    segment_type: "run",
    sequence_start: 3,
    monotonic_start_ns: startNs,
    wall_start: 0,
    state: "running",
    parent_task_id: null,
    coroutine_name: null,
    task_name: null,
    ...overrides,
  };
}

export function makeRenderSegment(
  segmentId: string,
  rowIndex: number,
  startSeconds: number,
  endSeconds: number,
  overrides: Partial<TimelineRenderSegment> = {},
): TimelineRenderSegment {
  return {
    segmentId,
    rowIndex,
    taskId: `task_${rowIndex}`,
    startSeconds,
    endSeconds,
    intent: "run",
    isActive: false,
    ...overrides,
  };
}

export function makeProjectionEntry(
  segmentId: string,
  rowIndex: number,
  startSeconds: number,
  endSeconds: number,
  overrides: Partial<TimelineRenderSegment> & {
    lifecycleState?: TimelineSegmentLifecycleState;
  } = {},
): TimelineSegmentProjectionEntry {
  return normalizeSegment(
    makeRenderSegment(segmentId, rowIndex, startSeconds, endSeconds, overrides),
  );
}
