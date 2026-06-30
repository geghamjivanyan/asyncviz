/**
 * Zustand-backed selectors that derive a :type:`TimelineRowProjection`
 * from the runtime store.
 *
 * The selectors keep dependency arrays minimal so React rerenders
 * exactly when the inputs change. Projection identity changes only
 * when one of the slices it reads changes — important because the
 * row renderer treats the projection reference as a memo key.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";
import {
  projectTimelineRows,
  type TimelineRowProjectionInputs,
} from "@/dashboard/timeline/rows/TimelineRowProjection";
import {
  EMPTY_TIMELINE_ROW_PROJECTION,
  type TimelineRowProjection,
} from "@/dashboard/timeline/rows/models/TimelineRowModels";
import { getTimelineRowMetrics } from "@/dashboard/timeline/rows/TimelineRowMetrics";
import { recordRowTrace } from "@/dashboard/timeline/rows/diagnostics/rowTrace";

export interface UseRowProjectionOptions {
  /** Optional override of the replay focus task. */
  focusedReplayTaskId?: string | null;
}

export function useTimelineRowProjection(
  options: UseRowProjectionOptions = {},
): TimelineRowProjection {
  const tasksById = useRuntimeStore((s) => s.tasksById);
  const warningsById = useRuntimeStore((s) => s.warnings.warningsById);
  const activeWarningIds = useRuntimeStore((s) => s.warnings.activeWarningIds);
  const sequence = useRuntimeStore((s) => s.lastSequence);

  const focusedReplayTaskId = options.focusedReplayTaskId ?? null;

  return useMemo(() => {
    if (Object.keys(tasksById).length === 0) return EMPTY_TIMELINE_ROW_PROJECTION;
    const activeWarnings = activeWarningIds
      .map((id) => warningsById[id])
      .filter((warning): warning is NonNullable<typeof warning> => warning !== undefined);
    const inputs: TimelineRowProjectionInputs = {
      tasksById,
      activeWarnings,
      replay:
        focusedReplayTaskId === null ? null : { sequence, focusedTaskId: focusedReplayTaskId },
      sequence,
    };
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const projection = projectTimelineRows(inputs);
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    getTimelineRowMetrics().recordProjection(end - start);
    recordRowTrace({
      kind: "projection",
      detail: `rows=${projection.totalRows} seq=${projection.sequence}`,
    });
    return projection;
  }, [tasksById, warningsById, activeWarningIds, sequence, focusedReplayTaskId]);
}
