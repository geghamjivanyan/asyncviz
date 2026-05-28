/**
 * Zustand-backed selectors for the event feed.
 *
 * The hooks here read minimal slices from the canonical runtime
 * store so React's render budget stays under control. Composition
 * happens in :func:`useProjectedEventRows` — selectors at the bottom
 * of the tree return references; the projection memo at the top
 * computes the array.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime/store";
import { useActiveWarnings } from "@/state/runtime/selectors";
import { projectEventRows } from "@/dashboard/events/selectors/projectEvents";
import type { EventRow } from "@/dashboard/events/models/eventRow";
import { getEventFeedMetrics } from "@/dashboard/events/observability";

export function useProjectedEventRows(): EventRow[] {
  const events = useRuntimeStore((s) => s.events);
  const tasksById = useRuntimeStore((s) => s.tasksById);
  const activeWarnings = useActiveWarnings();
  const activeSegmentsByTaskId = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);

  return useMemo(() => {
    const metrics = getEventFeedMetrics();
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const rows = projectEventRows({
      events,
      tasksById,
      activeWarnings,
      activeSegmentsByTaskId,
    });
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    metrics.recordProjection(rows.length, end - start);
    return rows;
  }, [events, tasksById, activeWarnings, activeSegmentsByTaskId]);
}
