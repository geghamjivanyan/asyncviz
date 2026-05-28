/**
 * Store-aware wrapper for the canvas timeline.
 *
 * Reads the projection from the runtime store, owns the local
 * camera + cursor state, and renders the canvas + the accessible
 * companion. Pointer interactions feed selection back into the store.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSelectedTaskId } from "@/state/runtime/selectors";
import { useTimelineProjection } from "@/dashboard/timeline/selectors/storeSelectors";
import {
  TimelineCanvas,
  type TimelineCanvasPointerEvent,
} from "@/dashboard/timeline/components/TimelineCanvas";
import { TimelineAccessibleSummary } from "@/dashboard/timeline/components/TimelineAccessibleSummary";
import { useTimelineCamera } from "@/dashboard/timeline/hooks/useTimelineCamera";
import { cn } from "@/lib/cn";
import type {
  TimelineRenderSegment,
  TimelineRow,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import type { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import { useTimelineLiveEngine } from "@/dashboard/timeline/live/hooks/useTimelineLiveEngine";
import { useTimelineVirtualization } from "@/dashboard/timeline/virtualization/hooks/useTimelineVirtualization";
import { useTimelineScaleEngine } from "@/dashboard/timeline/scaling/hooks/useTimelineScaleEngine";
import {
  useTimelineDataRange,
} from "@/dashboard/timeline/scaling/selectors/storeScaleSelectors";
import { useTimelineZoomController } from "@/dashboard/timeline/zoom/hooks/useTimelineZoomController";
import { useTimelineZoomShortcuts } from "@/dashboard/timeline/zoom/hooks/useTimelineZoomShortcuts";
import { useSelectedTaskSegmentRange } from "@/dashboard/timeline/zoom/selectors/storeZoomSelectors";
import { resolvePresets } from "@/dashboard/timeline/zoom/TimelineZoomPresets";
import { TimelineZoomControls } from "@/dashboard/timeline/zoom/TimelineZoomControls";
import { useTimelinePanController } from "@/dashboard/timeline/pan/hooks/useTimelinePanController";
import { useTimelinePanShortcuts } from "@/dashboard/timeline/pan/hooks/useTimelinePanShortcuts";
import { useTimelinePanDrag } from "@/dashboard/timeline/pan/hooks/useTimelinePanDrag";
import { TimelinePanToolbar } from "@/dashboard/timeline/pan/TimelinePanToolbar";
import { useTimelineSelectionController } from "@/dashboard/timeline/selection/hooks/useTimelineSelectionController";
import { useTimelineSelectionShortcuts } from "@/dashboard/timeline/selection/hooks/useTimelineSelectionShortcuts";
import {
  useSelectableRows,
  useTaskLookup,
  useTaskRangeLookup,
} from "@/dashboard/timeline/selection/selectors/storeSelectionSelectors";
import { makeRuntimeSelectionStore } from "@/dashboard/timeline/selection/TimelineSelectionStore";
import { TimelineSelectionToolbar } from "@/dashboard/timeline/selection/TimelineSelectionToolbar";
import {
  useFreezeRegionInteractions,
  useFreezeRegionLayer,
} from "@/dashboard/timeline/freeze_regions";
import type {
  FreezeRegionView,
} from "@/dashboard/timeline/freeze_regions";

export interface TimelineContainerProps {
  className?: string;
  /** Called whenever the timeline publishes its focus actions
   *  (reveal + fit). The dashboard's task inspector consumes these
   *  to drive its "Center / Fit" buttons without importing the
   *  selection controller. */
  onFocusActions?: (actions: { reveal: () => void; fit: () => void }) => void;
  /** Called when the operator clicks (or programmatically selects) a
   *  freeze region. Lets the host dashboard cross-link the warnings
   *  panel — e.g. open the panel inspector for the matching group. */
  onFreezeFocus?: (region: FreezeRegionView | null) => void;
}

export function TimelineContainer({
  className,
  onFocusActions,
  onFreezeFocus,
}: TimelineContainerProps) {
  const projection = useTimelineProjection();
  const selectedTaskId = useSelectedTaskId();
  const [renderer, setRenderer] = useState<TimelineRenderer | null>(null);
  // The live engine is the canonical realtime/redraw orchestrator —
  // it owns invalidation batching, replay coordination, and the
  // animation clock that drives active-segment evolution.
  const { engine: liveEngine } = useTimelineLiveEngine({ renderer });
  // The virtualization engine owns visible-window calculation,
  // row/segment culling, and cache reuse. Wired into the renderer so
  // it bypasses the inline cull on every frame.
  const { engine: virtualization } = useTimelineVirtualization<
    TimelineRow,
    TimelineRenderSegment
  >({ liveEngine });
  useEffect(() => {
    if (renderer === null) return;
    renderer.setVirtualizer(virtualization);
    return () => {
      renderer.setVirtualizer(null);
    };
  }, [renderer, virtualization]);

  const camera = useTimelineCamera({
    autoFitTo:
      projection.maxEndSeconds > projection.minStartSeconds
        ? { start: projection.minStartSeconds, end: projection.maxEndSeconds }
        : undefined,
  });

  // The scale engine mirrors the camera + canvas width into the
  // canonical time-axis transform. Consumers (hit testing, ticks,
  // future synchronized cursors) read the engine directly.
  const { engine: scaleEngine, scale: timeScale } = useTimelineScaleEngine({
    timeStart: camera.camera.timeStart,
    timeEnd: camera.camera.timeEnd,
  });

  // The zoom controller owns interactive viewport navigation. Every
  // toolbar button + keyboard shortcut routes through it.
  const { controller: zoomController, state: zoomState } = useTimelineZoomController({
    engine: scaleEngine,
  });

  // Resolve the pan bounds + range from the store first; the pan
  // controller consumes them.
  const dataRange = useTimelineDataRange();
  const selectionRange = useSelectedTaskSegmentRange();
  const panBounds = useMemo(
    () =>
      dataRange
        ? { minTimeSeconds: dataRange.startSeconds, maxTimeSeconds: dataRange.endSeconds }
        : undefined,
    [dataRange],
  );
  // The pan controller is the canonical chokepoint for every viewport
  // translation — drag, wheel, keyboard, presets.
  const { controller: panController, state: panState } = useTimelinePanController({
    engine: scaleEngine,
    bounds: panBounds,
  });

  // Mirror scale-engine changes initiated by the zoom OR pan
  // controller back into the camera so the renderer redraws. The
  // scale engine no-ops on identical keys, so the feedback loop
  // converges immediately.
  useEffect(() => {
    if (scaleEngine === null) return;
    const unsubscribe = scaleEngine.subscribe(() => {
      const s = scaleEngine.currentScale();
      camera.fitTo(s.timeStart, s.timeEnd);
      camera.disableAutoFit();
    });
    return unsubscribe;
  }, [scaleEngine, camera]);

  const presets = useMemo(
    () =>
      resolvePresets({
        dataRange,
        selectionRange,
      }),
    [dataRange, selectionRange],
  );

  useTimelineZoomShortcuts({
    controller: zoomController,
    fitRange: dataRange,
    resetRange: dataRange,
  });

  useTimelinePanShortcuts({
    controller: panController,
    dataRange,
  });

  // The selection controller is the canonical chokepoint for every
  // row-selection mutation — pointer clicks, keyboard nav, programmatic
  // toolbar actions, replay restore.
  const selectionStore = useMemo(() => makeRuntimeSelectionStore(), []);
  const selectableRows = useSelectableRows(projection.rows);
  const taskLookup = useTaskLookup();
  const taskRangeLookup = useTaskRangeLookup();
  const selectionRowSource = useMemo(
    () => ({
      getRows: () => selectableRows,
      getTask: (id: string | null) => taskLookup(id),
      getTaskRange: (id: string | null) => taskRangeLookup(id),
    }),
    [selectableRows, taskLookup, taskRangeLookup],
  );
  const selectionFocusAdapter = useMemo(() => {
    if (panController === null && zoomController === null) return null;
    return {
      panToTimeStart: (start: number) => panController?.panToTime(start),
      fitToRange: (s: number, e: number) =>
        zoomController?.zoomToRange(s, e, "fit-selection"),
    };
  }, [panController, zoomController]);
  const selectionViewportSource = useMemo(() => {
    return {
      getViewport: () => ({
        visibleStartSeconds: timeScale.timeStart,
        visibleEndSeconds: timeScale.timeEnd,
        durationSeconds: timeScale.durationSeconds,
      }),
    };
  }, [timeScale]);
  const { controller: selectionController, state: selectionState } =
    useTimelineSelectionController({
      store: selectionStore,
      rows: selectionRowSource,
      focus: selectionFocusAdapter,
      viewport: selectionViewportSource,
    });
  useTimelineSelectionShortcuts({ controller: selectionController });

  // Publish the controller's focus actions to upstream consumers
  // (the task inspector's "Center / Fit" buttons).
  useEffect(() => {
    if (onFocusActions === undefined) return;
    onFocusActions({
      reveal: () => selectionController.centerOnSelection(),
      fit: () => selectionController.fitToSelection(),
    });
  }, [selectionController, onFocusActions]);

  const dataset = useMemo<{
    rows: readonly TimelineRow[];
    segments: readonly TimelineRenderSegment[];
  }>(
    () => ({ rows: projection.rows, segments: projection.segments }),
    [projection.rows, projection.segments],
  );

  const [cursorSeconds, setCursorSeconds] = useState<number | null>(null);

  // Push the latest cursor time into the zoom controller so cursor-
  // anchored zooms (wheel, keyboard) pivot on it.
  useEffect(() => {
    zoomController?.setCursorTime(cursorSeconds);
  }, [zoomController, cursorSeconds]);

  // Freeze-region overlay: attach the canvas layer + hook pointer
  // interactions so clicks on a freeze body open the inspector.
  useFreezeRegionLayer(renderer);
  const freezeInteractions = useFreezeRegionInteractions({
    onSelect: onFreezeFocus,
  });

  const onPointerMove = useCallback(
    (event: TimelineCanvasPointerEvent) => {
      setCursorSeconds(event.timeSeconds);
      freezeInteractions.onPointerMove(event.xCss);
    },
    [freezeInteractions],
  );

  const onPointerLeave = useCallback(() => {
    setCursorSeconds(null);
    freezeInteractions.onPointerLeave();
  }, [freezeInteractions]);

  const onPointerDown = useCallback(
    (event: TimelineCanvasPointerEvent) => {
      // Freeze overlays sit above rows visually — give them first dibs.
      // A freeze hit selects the freeze + clears the row selection so
      // the operator sees the inspector without the canvas screaming
      // about a row that wasn't what they clicked on.
      const freezeHit = freezeInteractions.onPointerDown(event.xCss);
      if (freezeHit !== null) {
        selectionController.clearSelection("pointer");
        return;
      }
      const row = event.hit.row;
      if (row !== null) {
        selectionController.selectRow(row.taskId, "pointer");
      } else {
        selectionController.clearSelection("pointer");
      }
    },
    [freezeInteractions, selectionController],
  );

  // Bind the pan drag to the canvas DOM element. ``timeAt`` translates
  // pointer x into world time using the live scale.
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const onCanvasMount = useCallback((element: HTMLCanvasElement | null) => {
    canvasRef.current = element;
  }, []);
  const timeAt = useCallback(
    (pointerXCss: number): number => {
      if (timeScale === null) return 0;
      return timeScale.xToTime(pointerXCss);
    },
    [timeScale],
  );
  useTimelinePanDrag({
    targetRef: canvasRef,
    controller: panController,
    timeAt,
  });

  return (
    <div
      data-timeline-container="true"
      className={cn("flex h-full w-full min-h-0 min-w-0 flex-col", className)}
    >
      <TimelineZoomControls
        controller={zoomController}
        state={zoomState}
        fitAll={dataRange}
        presets={presets}
      />
      <TimelinePanToolbar
        controller={panController}
        state={panState}
        dataRange={dataRange}
      />
      <TimelineSelectionToolbar
        controller={selectionController}
        state={selectionState}
      />
      <TimelineCanvas
        camera={camera.camera}
        dataset={dataset}
        selectedTaskId={selectedTaskId}
        cursorTimeSeconds={cursorSeconds}
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
        onPointerDown={onPointerDown}
        onRendererMount={setRenderer}
        onCanvasMount={onCanvasMount}
      />
      <TimelineAccessibleSummary
        projection={projection}
        selectedTaskId={selectedTaskId}
        visibleWindow={virtualization.currentWindow()}
        timeScale={timeScale}
      />
    </div>
  );
}
