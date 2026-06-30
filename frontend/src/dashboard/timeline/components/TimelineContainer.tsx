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
import { useActiveSegmentCount } from "@/dashboard/timeline/live/selectors/storeLiveSelectors";
import { useTimelineVirtualization } from "@/dashboard/timeline/virtualization/hooks/useTimelineVirtualization";
import { useTimelineScaleEngine } from "@/dashboard/timeline/scaling/hooks/useTimelineScaleEngine";
import { useTimelineDataRange } from "@/dashboard/timeline/scaling/selectors/storeScaleSelectors";
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
import type { FreezeRegionView } from "@/dashboard/timeline/freeze_regions";

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
  const { engine: virtualization } = useTimelineVirtualization<TimelineRow, TimelineRenderSegment>({
    liveEngine,
  });
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
  //
  // The engine emits for both user gestures (zoom / pan / preset) and
  // our own echoes — every camera-state push flows back into the
  // engine via setTimeWindow, which re-emits. We track the latest
  // camera window in a ref so we can recognize the echo and skip
  // disabling autoFit; otherwise autoFit would flip off the first time
  // live data lands in the camera, freezing the live-follow behavior.
  const cameraWindowRef = useRef({
    start: camera.camera.timeStart,
    end: camera.camera.timeEnd,
  });
  cameraWindowRef.current = {
    start: camera.camera.timeStart,
    end: camera.camera.timeEnd,
  };
  useEffect(() => {
    if (scaleEngine === null) return;
    const unsubscribe = scaleEngine.subscribe(() => {
      const s = scaleEngine.currentScale();
      const cur = cameraWindowRef.current;
      const epsilon = Math.max(1e-6, Math.abs(cur.end - cur.start) * 1e-6);
      const isCameraEcho =
        Math.abs(s.timeStart - cur.start) <= epsilon && Math.abs(s.timeEnd - cur.end) <= epsilon;
      camera.fitTo(s.timeStart, s.timeEnd);
      if (!isCameraEcho) camera.disableAutoFit();
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
      fitToRange: (s: number, e: number) => zoomController?.zoomToRange(s, e, "fit-selection"),
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
  const { controller: selectionController, state: selectionState } = useTimelineSelectionController(
    {
      store: selectionStore,
      rows: selectionRowSource,
      focus: selectionFocusAdapter,
      viewport: selectionViewportSource,
    },
  );
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

  const isEmpty = projection.rows.length === 0;
  const activeSegmentCount = useActiveSegmentCount();

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
      <TimelinePanToolbar controller={panController} state={panState} dataRange={dataRange} />
      <TimelineSelectionToolbar controller={selectionController} state={selectionState} />
      <div className="relative flex min-h-0 flex-1">
        <TimelineLiveBadge activeSegmentCount={activeSegmentCount} />
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
        {isEmpty && (
          <div
            data-timeline-empty="true"
            className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1 px-6 text-center"
          >
            <p className="text-[10px] uppercase tracking-widest text-muted">No task activity yet</p>
            <p className="font-mono text-xs leading-relaxed text-subtle">
              Task lifecycles will appear here as your asyncio runtime emits events. Each row is a
              task; each bar is a span of its lifecycle.
            </p>
          </div>
        )}
      </div>
      <TimelineAccessibleSummary
        projection={projection}
        selectedTaskId={selectedTaskId}
        visibleWindow={virtualization.currentWindow()}
        timeScale={timeScale}
      />
    </div>
  );
}

function TimelineLiveBadge({ activeSegmentCount }: { activeSegmentCount: number }) {
  const isLive = activeSegmentCount > 0;
  return (
    <div
      data-timeline-live-badge="true"
      data-live={isLive ? "true" : "false"}
      role="status"
      aria-live="polite"
      className={cn(
        "pointer-events-none absolute right-3 top-3 z-10",
        "flex items-center gap-1.5 rounded-full border bg-canvas/85 px-2 py-0.5",
        "font-mono text-[10px] uppercase tracking-widest backdrop-blur-sm",
        isLive ? "border-success/60 text-success" : "border-line text-muted",
      )}
    >
      <span
        aria-hidden="true"
        className={cn("h-1.5 w-1.5 rounded-full", isLive ? "animate-pulse bg-success" : "bg-muted")}
      />
      {isLive ? `Live · ${activeSegmentCount} active` : "Idle"}
    </div>
  );
}
