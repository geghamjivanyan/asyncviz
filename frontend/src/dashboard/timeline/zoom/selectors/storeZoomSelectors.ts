/**
 * Tiny store selectors for the zoom controller integration.
 *
 * The selectors mirror the surface the existing scale selectors
 * expose so the React glue can stay symmetric across the engines.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";

/** Range covered by the selected task's closed segments — drives the
 *  ``fit-selection`` preset. Returns ``null`` when no selection or
 *  the selection has no segments. */
export function useSelectedTaskSegmentRange(): {
  startSeconds: number;
  endSeconds: number;
} | null {
  const selectedTaskId = useRuntimeStore((s) => s.selectedTaskId);
  const segmentIdsByTaskId = useRuntimeStore((s) => s.timeline.segmentIdsByTaskId);
  const segmentsById = useRuntimeStore((s) => s.timeline.segmentsById);
  const activeByTask = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  return useMemo(() => {
    if (selectedTaskId === null) return null;
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    const segmentIds = segmentIdsByTaskId[selectedTaskId] ?? [];
    for (const id of segmentIds) {
      const segment = segmentsById[id];
      if (segment === undefined) continue;
      const s = segment.monotonic_start_ns / 1e9;
      const e = segment.monotonic_end_ns / 1e9;
      if (s < min) min = s;
      if (e > max) max = e;
    }
    const active = activeByTask[selectedTaskId];
    if (active !== undefined) {
      const s = active.monotonic_start_ns / 1e9;
      if (s < min) min = s;
      if (s > max) max = s;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    return { startSeconds: min, endSeconds: Math.max(max, min + 1) };
  }, [selectedTaskId, segmentIdsByTaskId, segmentsById, activeByTask]);
}
