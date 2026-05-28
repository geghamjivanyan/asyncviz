/**
 * Tiny Zustand-backed selectors that surface the data the
 * selection controller depends on.
 */

import { useMemo } from "react";
import type { TaskSnapshot } from "@/types/runtime";
import { useRuntimeStore } from "@/state/runtime";
import type {
  SelectableRow,
} from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

/** Stable selectable-row list derived from the row projection used
 *  by the canvas — keeps deterministic ordering (created_at + task
 *  id) so navigation matches the rendered row order. */
export function useSelectableRows(
  rows: readonly { rowIndex: number; taskId: string }[],
): readonly SelectableRow[] {
  return useMemo(
    () => rows.map((row) => ({ rowIndex: row.rowIndex, taskId: row.taskId })),
    [rows],
  );
}

/** Snapshot lookup helper. */
export function useTaskLookup(): (taskId: string | null) => TaskSnapshot | null {
  const tasksById = useRuntimeStore((s) => s.tasksById);
  return useMemo(
    () => (taskId: string | null) => (taskId === null ? null : tasksById[taskId] ?? null),
    [tasksById],
  );
}

/** Time-range lookup for a task — fans out into the timeline's
 *  closed + active segments. Returns ``null`` when no segments are
 *  known for the task. */
export function useTaskRangeLookup(): (taskId: string | null) =>
  | { startSeconds: number; endSeconds: number }
  | null {
  const segmentIdsByTaskId = useRuntimeStore((s) => s.timeline.segmentIdsByTaskId);
  const segmentsById = useRuntimeStore((s) => s.timeline.segmentsById);
  const activeByTask = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  return useMemo(
    () => (taskId: string | null) => {
      if (taskId === null) return null;
      let min = Number.POSITIVE_INFINITY;
      let max = Number.NEGATIVE_INFINITY;
      const ids = segmentIdsByTaskId[taskId] ?? [];
      for (const id of ids) {
        const segment = segmentsById[id];
        if (segment === undefined) continue;
        const s = segment.monotonic_start_ns / 1e9;
        const e = segment.monotonic_end_ns / 1e9;
        if (s < min) min = s;
        if (e > max) max = e;
      }
      const active = activeByTask[taskId];
      if (active !== undefined) {
        const s = active.monotonic_start_ns / 1e9;
        if (s < min) min = s;
        if (s > max) max = s;
      }
      if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
      return { startSeconds: min, endSeconds: Math.max(max, min + 1) };
    },
    [segmentIdsByTaskId, segmentsById, activeByTask],
  );
}
