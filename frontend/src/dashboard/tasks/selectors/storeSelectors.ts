/**
 * Zustand-backed selectors for the live task table.
 *
 * The hooks here read minimal slices from the canonical runtime store
 * so React's render budget stays under control. Composition happens
 * in :func:`useProjectedTaskRows` — selectors at the bottom of the
 * tree return references; the projection memo at the top computes
 * the array.
 *
 * No hook here calls another component; they are safe to use in any
 * place that already has the canonical providers mounted (i.e.
 * everywhere :class:`AppProviders` reaches).
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime/store";
import { useActiveWarnings } from "@/state/runtime/selectors";
import type { TaskRow } from "@/dashboard/tasks/models/taskRow";
import { projectTaskRows } from "@/dashboard/tasks/selectors/projectRows";
import { getTaskTableMetrics } from "@/dashboard/tasks/observability/tableMetrics";

/**
 * Project the canonical store state into a stable :type:`TaskRow`
 * array. Sorted by ``createdAt`` / ``taskId`` for deterministic
 * ordering. Output identity changes only when the underlying inputs
 * change.
 */
export function useProjectedTaskRows(): TaskRow[] {
  const tasksById = useRuntimeStore((s) => s.tasksById);
  const activeWarnings = useActiveWarnings();
  const activeSegmentsByTaskId = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  const segmentIdsByTaskId = useRuntimeStore((s) => s.timeline.segmentIdsByTaskId);
  const replayWindowHit = useRuntimeStore((s) => s.replay.windowHit);
  const lastSequence = useRuntimeStore((s) => s.lastSequence);
  const deltaCounts = useRuntimeStore((s) => s.metrics.deltaCounts);
  // ``isReplay`` flips to ``true`` only when the snapshot didn't cover the
  // requested window — the rows are then displayed as "replaying" until a
  // delta lands.
  const isReplay = !replayWindowHit && lastSequence === 0;

  const metricsTouchedTaskIds = useMemo<ReadonlySet<string>>(() => {
    // Today the metrics deltas don't carry task_id targets; the
    // ``recentlyTouched`` flag is reserved for future per-task overlays.
    // We expose an empty set so consumers can already type against it.
    void deltaCounts;
    return new Set<string>();
  }, [deltaCounts]);

  return useMemo(() => {
    const metrics = getTaskTableMetrics();
    metrics.recordSelectorEvaluation();
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const rows = projectTaskRows({
      tasksById,
      activeWarnings,
      activeSegmentsByTaskId,
      segmentIdsByTaskId,
      isReplay,
      metricsTouchedTaskIds,
    });
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    metrics.recordProjection(rows.length, end - start);
    return rows;
  }, [
    tasksById,
    activeWarnings,
    activeSegmentsByTaskId,
    segmentIdsByTaskId,
    isReplay,
    metricsTouchedTaskIds,
  ]);
}

/** Pluck a single projected row by id. Returns ``undefined`` when the
 *  row is no longer present. */
export function useProjectedTaskRow(taskId: string | null): TaskRow | undefined {
  const rows = useProjectedTaskRows();
  return useMemo(() => {
    if (taskId === null) return undefined;
    return rows.find((row) => row.taskId === taskId);
  }, [rows, taskId]);
}
