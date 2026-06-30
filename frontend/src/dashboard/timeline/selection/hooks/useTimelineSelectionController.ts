/**
 * React glue for the canonical :class:`TimelineSelectionController`.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  TimelineSelectionController,
  type SelectionFocusAdapter,
  type SelectionRowSource,
  type SelectionViewportSource,
  type TimelineSelectionControllerOptions,
} from "@/dashboard/timeline/selection/TimelineSelectionController";
import type { TimelineSelectionState } from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

export interface UseTimelineSelectionControllerArgs extends Omit<
  TimelineSelectionControllerOptions,
  "rows" | "viewport" | "focus"
> {
  rows: SelectionRowSource;
  viewport?: SelectionViewportSource | null;
  focus?: SelectionFocusAdapter | null;
}

export interface UseTimelineSelectionControllerResult {
  controller: TimelineSelectionController;
  state: TimelineSelectionState;
}

export function useTimelineSelectionController(
  args: UseTimelineSelectionControllerArgs,
): UseTimelineSelectionControllerResult {
  // Stable refs so the controller never sees stale projections /
  // viewport adapters even though React rerenders constantly.
  const rowsRef = useRef<SelectionRowSource>(args.rows);
  rowsRef.current = args.rows;
  const viewportRef = useRef<SelectionViewportSource | null>(args.viewport ?? null);
  viewportRef.current = args.viewport ?? null;
  const focusRef = useRef<SelectionFocusAdapter | null>(args.focus ?? null);
  focusRef.current = args.focus ?? null;

  const controller = useMemo(() => {
    return new TimelineSelectionController({
      store: args.store,
      rows: {
        getRows: () => rowsRef.current.getRows(),
        getTask: (id) => rowsRef.current.getTask(id),
        getTaskRange: (id) => rowsRef.current.getTaskRange(id),
      },
      viewport: {
        getViewport: () =>
          viewportRef.current?.getViewport() ?? {
            visibleStartSeconds: 0,
            visibleEndSeconds: 1,
            durationSeconds: 1,
          },
      },
      focus: {
        panToTimeStart: (start) => focusRef.current?.panToTimeStart(start),
        fitToRange: (s, e) => focusRef.current?.fitToRange(s, e),
      },
      metrics: args.metrics,
      config: args.config,
    });
    // The controller is one-shot per host. Tests can recreate it by
    // remounting.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [args.store]);

  const [state, setState] = useState<TimelineSelectionState>(() => controller.currentState());

  useEffect(() => {
    setState(controller.currentState());
    const unsubscribe = controller.subscribe((next) => setState(next));
    return unsubscribe;
  }, [controller]);

  // Refresh the controller's state whenever the row list changes so
  // ``selectedRowIndex`` + ``atFirst`` / ``atLast`` stay accurate.
  useEffect(() => {
    controller.refresh();
  }, [controller, args.rows]);

  useEffect(() => {
    return () => {
      controller.dispose();
    };
  }, [controller]);

  return { controller, state };
}
