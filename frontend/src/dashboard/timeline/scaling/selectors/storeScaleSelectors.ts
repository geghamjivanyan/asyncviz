/**
 * Tiny selectors for the scale engine.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";

/** Minimum + maximum monotonic timestamps across all known segments —
 *  drives the engine's "fit to data" calls. Returns ``null`` when
 *  no data exists. */
export function useTimelineDataRange(): { startSeconds: number; endSeconds: number } | null {
  const segmentsById = useRuntimeStore((s) => s.timeline.segmentsById);
  const activeByTask = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  return useMemo(() => {
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (const segment of Object.values(segmentsById)) {
      const s = segment.monotonic_start_ns / 1e9;
      const e = segment.monotonic_end_ns / 1e9;
      if (s < min) min = s;
      if (e > max) max = e;
    }
    for (const active of Object.values(activeByTask)) {
      const s = active.monotonic_start_ns / 1e9;
      if (s < min) min = s;
      if (s > max) max = s;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    return { startSeconds: min, endSeconds: Math.max(max, min + 1) };
  }, [segmentsById, activeByTask]);
}
