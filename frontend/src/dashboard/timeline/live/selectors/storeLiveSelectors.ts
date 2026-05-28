/**
 * Tiny selectors that surface the data the live engine consumes from
 * the runtime store.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";

/** Number of currently-active timeline segments — drives the engine's
 *  animation clock. */
export function useActiveSegmentCount(): number {
  const activeMap = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  return useMemo(() => Object.keys(activeMap).length, [activeMap]);
}

/** Highest sequence cursor the store has applied — useful for the
 *  engine's stale-suppression guard if it ever gates on it. */
export function useLastAppliedSequence(): number {
  return useRuntimeStore((s) => s.lastSequence);
}
