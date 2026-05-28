/**
 * Zustand-backed selectors that build a :type:`TimelineSegmentProjection`
 * directly from the runtime store.
 *
 * The selector pairs with :func:`useTimelineProjection` — the segment
 * projection is a strict superset of the data already in the render
 * dataset but in a shape that's friendlier for hit testing, grouping,
 * and diagnostics.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";
import {
  projectTimelineSegments,
  type TimelineSegmentProjectionInputs,
} from "@/dashboard/timeline/segments/TimelineSegmentProjection";
import {
  EMPTY_TIMELINE_SEGMENT_PROJECTION,
  type TimelineSegmentProjection,
} from "@/dashboard/timeline/segments/models/TimelineSegmentModels";
import { getTimelineSegmentMetrics } from "@/dashboard/timeline/segments/TimelineSegmentMetrics";
import { recordSegmentTrace } from "@/dashboard/timeline/segments/diagnostics/segmentTrace";

export interface UseSegmentProjectionOptions {
  focusedReplaySegmentId?: string | null;
  focusedReplayTaskId?: string | null;
}

export function useTimelineSegmentProjection(
  options: UseSegmentProjectionOptions = {},
): TimelineSegmentProjection {
  const tasksById = useRuntimeStore((s) => s.tasksById);
  const segmentsById = useRuntimeStore((s) => s.timeline.segmentsById);
  const segmentIdsByTaskId = useRuntimeStore((s) => s.timeline.segmentIdsByTaskId);
  const activeSegmentsByTaskId = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  const warningsById = useRuntimeStore((s) => s.warnings.warningsById);
  const activeWarningIds = useRuntimeStore((s) => s.warnings.activeWarningIds);
  const sequence = useRuntimeStore((s) => s.lastSequence);

  const focusedReplaySegmentId = options.focusedReplaySegmentId ?? null;
  const focusedReplayTaskId = options.focusedReplayTaskId ?? null;

  return useMemo(() => {
    if (Object.keys(tasksById).length === 0) return EMPTY_TIMELINE_SEGMENT_PROJECTION;
    const activeWarnings = activeWarningIds
      .map((id) => warningsById[id])
      .filter((warning): warning is NonNullable<typeof warning> => warning !== undefined);
    const inputs: TimelineSegmentProjectionInputs = {
      tasksById,
      segmentsById,
      segmentIdsByTaskId,
      activeSegmentsByTaskId,
      activeWarnings,
      replay:
        focusedReplaySegmentId === null && focusedReplayTaskId === null
          ? null
          : {
              sequence,
              focusedSegmentId: focusedReplaySegmentId,
              focusedTaskId: focusedReplayTaskId,
            },
      sequence,
    };
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const projection = projectTimelineSegments(inputs);
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    getTimelineSegmentMetrics().recordProjection(end - start);
    recordSegmentTrace({
      kind: "projection",
      detail: `total=${projection.totalSegments} seq=${projection.sequence}`,
    });
    return projection;
  }, [
    tasksById,
    segmentsById,
    segmentIdsByTaskId,
    activeSegmentsByTaskId,
    warningsById,
    activeWarningIds,
    sequence,
    focusedReplaySegmentId,
    focusedReplayTaskId,
  ]);
}
