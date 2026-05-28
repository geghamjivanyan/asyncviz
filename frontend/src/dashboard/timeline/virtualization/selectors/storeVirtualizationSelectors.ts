/**
 * Tiny selectors for the virtualization engine — surface the runtime
 * store's totals the engine needs to size its caches.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";

/** Number of tasks currently tracked — used as the upper bound on
 *  the row count by the virtualization engine. */
export function useTaskCount(): number {
  const tasksById = useRuntimeStore((s) => s.tasksById);
  return useMemo(() => Object.keys(tasksById).length, [tasksById]);
}

/** Total finalized segments + active segments. */
export function useSegmentCount(): number {
  const segmentsById = useRuntimeStore((s) => s.timeline.segmentsById);
  const activeByTask = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  return useMemo(
    () => Object.keys(segmentsById).length + Object.keys(activeByTask).length,
    [segmentsById, activeByTask],
  );
}
