/**
 * React glue for the canonical :class:`TimelinePanController`.
 */

import { useEffect, useMemo, useState } from "react";
import {
  TimelinePanController,
  type TimelinePanControllerOptions,
} from "@/dashboard/timeline/pan/TimelinePanController";
import type { TimelinePanState } from "@/dashboard/timeline/pan/models/TimelinePanModels";

export interface UseTimelinePanControllerArgs
  extends Omit<TimelinePanControllerOptions, "engine"> {
  engine: TimelinePanControllerOptions["engine"] | null;
}

export interface UseTimelinePanControllerResult {
  controller: TimelinePanController | null;
  state: TimelinePanState | null;
}

export function useTimelinePanController(
  args: UseTimelinePanControllerArgs,
): UseTimelinePanControllerResult {
  const controller = useMemo(() => {
    if (args.engine === null) return null;
    return new TimelinePanController({
      engine: args.engine,
      metrics: args.metrics,
      config: args.config,
      bounds: args.bounds,
      momentum: args.momentum,
    });
    // Constructed once per engine.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [args.engine]);

  const [state, setState] = useState<TimelinePanState | null>(() =>
    controller ? controller.currentState() : null,
  );

  useEffect(() => {
    if (controller === null) {
      setState(null);
      return;
    }
    setState(controller.currentState());
    const unsubscribe = controller.subscribe((next) => setState(next));
    return unsubscribe;
  }, [controller]);

  // Sync bounds when they change (engine reference is stable).
  useEffect(() => {
    if (controller === null) return;
    controller.setBounds(args.bounds ?? null);
  }, [controller, args.bounds]);

  useEffect(() => {
    return () => {
      controller?.dispose();
    };
  }, [controller]);

  return { controller, state };
}
