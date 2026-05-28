/**
 * Zustand-backed selectors for the timeline renderer.
 *
 * Reads minimal store slices; composes them through the pure
 * projection. Output identity changes only when the inputs change.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";
import {
  EMPTY_PROJECTION,
  projectTimeline,
  type TimelineProjection,
} from "@/dashboard/timeline/selectors/projectTimeline";

export function useTimelineProjection(): TimelineProjection {
  const tasksById = useRuntimeStore((s) => s.tasksById);
  const segmentsById = useRuntimeStore((s) => s.timeline.segmentsById);
  const segmentIdsByTaskId = useRuntimeStore((s) => s.timeline.segmentIdsByTaskId);
  const activeSegmentsByTaskId = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  const warningsById = useRuntimeStore((s) => s.warnings.warningsById);
  const activeWarningIds = useRuntimeStore((s) => s.warnings.activeWarningIds);
  return useMemo(() => {
    if (Object.keys(tasksById).length === 0) return EMPTY_PROJECTION;
    const activeWarnings = activeWarningIds
      .map((id) => warningsById[id])
      .filter((warning): warning is NonNullable<typeof warning> => warning !== undefined);
    return projectTimeline({
      tasksById,
      segmentsById,
      segmentIdsByTaskId,
      activeSegmentsByTaskId,
      activeWarnings,
    });
  }, [tasksById, segmentsById, segmentIdsByTaskId, activeSegmentsByTaskId, warningsById, activeWarningIds]);
}
