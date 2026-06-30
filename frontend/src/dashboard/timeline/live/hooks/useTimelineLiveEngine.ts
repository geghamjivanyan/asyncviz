/**
 * React glue for the canonical :class:`TimelineLiveEngine`.
 *
 * Creates an engine bound to the supplied :class:`TimelineRenderer`,
 * wires it to the runtime websocket client (when one is provided),
 * and keeps its animation clock in sync with the store's active
 * segment count.
 *
 * The hook is the *only* React-side surface the engine exposes —
 * everything else stays framework-free.
 */

import { useEffect, useMemo } from "react";
import type { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import type { RuntimeWebSocketClient } from "@/runtime/websocket";
import {
  TimelineLiveEngine,
  type TimelineLiveEngineOptions,
} from "@/dashboard/timeline/live/TimelineLiveEngine";
import { bindLiveEngineToClient } from "@/dashboard/timeline/live/TimelineUpdateCoordinator";
import { useActiveSegmentCount } from "@/dashboard/timeline/live/selectors/storeLiveSelectors";

export interface UseTimelineLiveEngineArgs {
  renderer: TimelineRenderer | null;
  client?: RuntimeWebSocketClient | null;
  options?: Omit<TimelineLiveEngineOptions, "renderer">;
}

export interface UseTimelineLiveEngineResult {
  engine: TimelineLiveEngine | null;
}

export function useTimelineLiveEngine(
  args: UseTimelineLiveEngineArgs,
): UseTimelineLiveEngineResult {
  const { renderer, client, options } = args;

  const engine = useMemo(() => {
    if (renderer === null) return null;
    return new TimelineLiveEngine({ renderer, ...(options ?? {}) });
    // The engine is one-shot per renderer instance — options changes
    // are not propagated. Callers that need different options should
    // remount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renderer]);

  // Wire to the websocket client when one is provided.
  useEffect(() => {
    if (engine === null || !client) return;
    const binding = bindLiveEngineToClient({ engine, client });
    return () => binding.unbind();
  }, [engine, client]);

  // Active-segment count → animation clock.
  const activeCount = useActiveSegmentCount();
  useEffect(() => {
    if (engine === null) return;
    engine.setActiveSegmentCount(activeCount);
  }, [engine, activeCount]);

  // Tear the engine down on unmount.
  useEffect(() => {
    return () => {
      engine?.dispose();
    };
  }, [engine]);

  return { engine };
}
