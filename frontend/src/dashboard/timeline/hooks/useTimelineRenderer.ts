/**
 * React lifecycle for the canvas :class:`TimelineRenderer`.
 *
 * Owns:
 *
 *   * the renderer instance,
 *   * its default layer set (grid + segments + selection + overlay),
 *   * propagating viewport / camera / dataset / selection / cursor
 *     updates from the consumer hook tree.
 *
 * The consumer mounts a ``<canvas>`` and passes the ref + viewport +
 * camera + dataset. The hook handles the rest.
 */

import { useEffect, useMemo, useRef } from "react";
import type { TimelineCamera } from "@/dashboard/timeline/viewport/TimelineCamera";
import type { TimelineViewport } from "@/dashboard/timeline/viewport/TimelineViewport";
import {
  EMPTY_DATASET,
  TimelineRenderer,
  type TimelineDataset,
} from "@/dashboard/timeline/rendering/TimelineRenderer";
import { GridLayer } from "@/dashboard/timeline/rendering/GridLayer";
import { SelectionLayer } from "@/dashboard/timeline/rendering/SelectionLayer";
import { OverlayLayer } from "@/dashboard/timeline/rendering/OverlayLayer";
import { TimelineRowRenderer } from "@/dashboard/timeline/rows/TimelineRowRenderer";
import { TimelineSegmentRenderer } from "@/dashboard/timeline/segments/TimelineSegmentRenderer";
import type { TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";
import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import type { SchedulerOptions } from "@/dashboard/timeline/scheduler/TimelineScheduler";

export interface UseTimelineRendererOptions {
  /** Override the default layer set (grid + segments + selection + overlay). */
  layers?: readonly TimelineLayer[];
  palette?: TimelineColorPalette;
  scheduler?: SchedulerOptions;
}

export interface TimelineRendererControl {
  /** Force a synchronous render — useful for the initial mount. */
  forceRender: () => void;
  /** Underlying renderer instance — exposed for advanced use cases. */
  renderer: TimelineRenderer;
}

export function useTimelineRenderer(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  viewport: TimelineViewport,
  camera: TimelineCamera,
  dataset: TimelineDataset = EMPTY_DATASET,
  selectedTaskId: string | null = null,
  cursorTimeSeconds: number | null = null,
  options: UseTimelineRendererOptions = {},
): TimelineRendererControl {
  const rendererRef = useRef<TimelineRenderer | null>(null);

  // Construct the renderer + default layers exactly once.
  const renderer = useMemo(() => {
    const instance = new TimelineRenderer({
      palette: options.palette,
      scheduler: options.scheduler,
    });
    const rowController = new TimelineRowRenderer();
    const segmentRenderer = new TimelineSegmentRenderer({
      rowLayout: rowController.getLayout(),
    });
    const layers = options.layers ?? [
      new GridLayer(),
      rowController.background,
      segmentRenderer,
      new SelectionLayer(),
      rowController.foreground,
      new OverlayLayer(),
    ];
    for (const layer of layers) instance.addLayer(layer);
    rendererRef.current = instance;
    return instance;
    // The renderer is intentionally one-shot — recreating on prop
    // changes would discard scheduler + metrics state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Attach / detach the canvas.
  useEffect(() => {
    renderer.attachCanvas(canvasRef.current);
    return () => {
      renderer.attachCanvas(null);
    };
  }, [canvasRef, renderer]);

  useEffect(() => () => renderer.dispose(), [renderer]);

  // Sync viewport / camera / dataset / selection / cursor.
  useEffect(() => {
    renderer.setViewport(viewport);
  }, [renderer, viewport]);

  useEffect(() => {
    renderer.setCamera(camera);
  }, [renderer, camera]);

  useEffect(() => {
    renderer.setDataset(dataset);
  }, [renderer, dataset]);

  useEffect(() => {
    renderer.setSelectedTaskId(selectedTaskId);
  }, [renderer, selectedTaskId]);

  useEffect(() => {
    renderer.setCursorTimeSeconds(cursorTimeSeconds);
  }, [renderer, cursorTimeSeconds]);

  useEffect(() => {
    if (options.palette !== undefined) renderer.setPalette(options.palette);
  }, [renderer, options.palette]);

  return {
    forceRender: () => renderer.forceRender(),
    renderer,
  };
}
