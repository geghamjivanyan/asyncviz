/**
 * React glue for the canonical :class:`TimelineScaleEngine`.
 *
 * Owns the engine instance and keeps its viewport + time-window
 * synchronized with the consumer's camera/viewport state. The hook
 * is intentionally thin — the engine is framework-free; this just
 * makes its lifecycle easy to manage from React.
 */

import { useEffect, useMemo, useState } from "react";
import {
  TimelineScaleEngine,
  type TimelineScaleEngineOptions,
} from "@/dashboard/timeline/scaling/TimelineScaleEngine";
import type { TimelineTimeScale } from "@/dashboard/timeline/scaling/TimelineTimeScale";
import type { ScaleViewport } from "@/dashboard/timeline/scaling/TimelineScaleViewport";

export interface UseTimelineScaleEngineArgs {
  options?: TimelineScaleEngineOptions;
  /** Optional viewport to push into the engine on changes. */
  viewport?: ScaleViewport;
  /** Optional time window to push into the engine. */
  timeStart?: number;
  timeEnd?: number;
}

export interface UseTimelineScaleEngineResult {
  engine: TimelineScaleEngine;
  /** Latest scale snapshot — React-friendly handle. */
  scale: TimelineTimeScale;
}

export function useTimelineScaleEngine(
  args: UseTimelineScaleEngineArgs = {},
): UseTimelineScaleEngineResult {
  const engine = useMemo(
    () => new TimelineScaleEngine(args.options),
    // Engine is one-shot per host — option changes don't recreate it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const [scale, setScale] = useState<TimelineTimeScale>(() => engine.currentScale());

  useEffect(() => {
    const unsubscribe = engine.subscribe(() => {
      setScale(engine.currentScale());
    });
    return unsubscribe;
  }, [engine]);

  useEffect(() => {
    if (args.viewport) engine.setViewport(args.viewport);
  }, [engine, args.viewport]);

  useEffect(() => {
    if (args.timeStart !== undefined && args.timeEnd !== undefined) {
      engine.setTimeWindow(args.timeStart, args.timeEnd);
    }
  }, [engine, args.timeStart, args.timeEnd]);

  return { engine, scale };
}
