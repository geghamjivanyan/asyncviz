/**
 * React canvas component that mounts the timeline renderer.
 *
 * The component owns the DOM element + resize lifecycle. Visual
 * drawing is delegated to :class:`TimelineRenderer`. Pointer events
 * stream into the supplied handlers — already translated into world
 * coordinates so the consumer doesn't need to re-derive the
 * coordinate system.
 */

import { useCallback, useEffect, useRef, type PointerEvent as ReactPointerEvent } from "react";
import { useElementViewport } from "@/dashboard/timeline/hooks/useResizeObserver";
import { useTimelineRenderer } from "@/dashboard/timeline/hooks/useTimelineRenderer";
import type { TimelineCamera } from "@/dashboard/timeline/viewport/TimelineCamera";
import type {
  TimelineDataset,
  TimelineRenderer,
} from "@/dashboard/timeline/rendering/TimelineRenderer";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { hitTest, type HitTestResult } from "@/dashboard/timeline/interaction/TimelineHitTesting";
import { cn } from "@/lib/cn";

export interface TimelineCanvasPointerEvent {
  xCss: number;
  yCss: number;
  timeSeconds: number;
  rowIndex: number;
  hit: HitTestResult;
}

export interface TimelineCanvasProps {
  camera: TimelineCamera;
  dataset: TimelineDataset;
  selectedTaskId: string | null;
  cursorTimeSeconds: number | null;
  onPointerMove?: (event: TimelineCanvasPointerEvent) => void;
  onPointerLeave?: () => void;
  onPointerDown?: (event: TimelineCanvasPointerEvent) => void;
  className?: string;
  /** Accessible label for the canvas region. */
  ariaLabel?: string;
  /** Fires when the underlying renderer is created — used by the live
   *  engine glue so it can register itself without lifting the
   *  renderer creation. */
  onRendererMount?: (renderer: TimelineRenderer | null) => void;
  /** Fires when the canvas DOM element is mounted — used by the pan
   *  controller's drag hook to bind pointer events. */
  onCanvasMount?: (element: HTMLCanvasElement | null) => void;
}

export function TimelineCanvas({
  camera,
  dataset,
  selectedTaskId,
  cursorTimeSeconds,
  onPointerMove,
  onPointerLeave,
  onPointerDown,
  className,
  ariaLabel = "Timeline canvas",
  onRendererMount,
  onCanvasMount,
}: TimelineCanvasProps) {
  const { ref: containerRef, viewport } = useElementViewport();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { renderer } = useTimelineRenderer(
    canvasRef,
    viewport,
    camera,
    dataset,
    selectedTaskId,
    cursorTimeSeconds,
  );
  useEffect(() => {
    onRendererMount?.(renderer);
    return () => {
      onRendererMount?.(null);
    };
  }, [renderer, onRendererMount]);
  useEffect(() => {
    onCanvasMount?.(canvasRef.current);
    return () => {
      onCanvasMount?.(null);
    };
  }, [onCanvasMount]);

  const translateEvent = useCallback(
    (event: ReactPointerEvent<HTMLCanvasElement>): TimelineCanvasPointerEvent => {
      const rect = event.currentTarget.getBoundingClientRect();
      const xCss = event.clientX - rect.left;
      const yCss = event.clientY - rect.top;
      const coords = new TimelineCoordinateSystem(camera, viewport);
      const hit = hitTest({
        xCss,
        yCss,
        coords,
        rows: dataset.rows,
        segments: dataset.segments,
      });
      return {
        xCss,
        yCss,
        timeSeconds: coords.xToTime(xCss),
        rowIndex: Math.floor(coords.yToRow(yCss)),
        hit,
      };
    },
    [camera, viewport, dataset.rows, dataset.segments],
  );

  const handlePointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (onPointerMove === undefined) return;
    onPointerMove(translateEvent(event));
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (onPointerDown === undefined) return;
    onPointerDown(translateEvent(event));
  };

  return (
    <div
      ref={containerRef}
      data-timeline-canvas-region="true"
      className={cn("relative h-full w-full min-h-0 min-w-0 overflow-hidden", className)}
    >
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={ariaLabel}
        onPointerMove={handlePointerMove}
        onPointerLeave={onPointerLeave}
        onPointerDown={handlePointerDown}
        className="block h-full w-full"
      />
    </div>
  );
}
