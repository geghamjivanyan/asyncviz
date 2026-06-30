/**
 * React glue for the canonical :class:`TimelineZoomController`.
 *
 * Constructs the controller (one per host), subscribes to its state
 * updates, and disposes cleanly on unmount.
 */

import { useEffect, useMemo, useState } from "react";
import {
  TimelineZoomController,
  type TimelineZoomControllerOptions,
} from "@/dashboard/timeline/zoom/TimelineZoomController";
import type { TimelineZoomState } from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

export interface UseTimelineZoomControllerArgs extends Omit<
  TimelineZoomControllerOptions,
  "engine"
> {
  engine: TimelineZoomControllerOptions["engine"] | null;
}

export interface UseTimelineZoomControllerResult {
  controller: TimelineZoomController | null;
  state: TimelineZoomState | null;
}

export function useTimelineZoomController(
  args: UseTimelineZoomControllerArgs,
): UseTimelineZoomControllerResult {
  const controller = useMemo(() => {
    if (args.engine === null) return null;
    return new TimelineZoomController({
      engine: args.engine,
      metrics: args.metrics,
      config: args.config,
    });
    // The controller is one-shot per engine — option changes don't
    // recreate it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [args.engine]);

  const [state, setState] = useState<TimelineZoomState | null>(() =>
    controller ? controller.currentState() : null,
  );

  useEffect(() => {
    if (controller === null) {
      setState(null);
      return;
    }
    setState(controller.currentState());
    const unsubscribe = controller.subscribe((next) => {
      setState(next);
    });
    return () => {
      unsubscribe();
    };
  }, [controller]);

  useEffect(() => {
    return () => {
      controller?.dispose();
    };
  }, [controller]);

  return { controller, state };
}
