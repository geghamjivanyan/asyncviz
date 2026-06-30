/**
 * Canonical timeline renderer.
 *
 * Ties together:
 *
 *   * a :class:`HTMLCanvasElement` (or any object that gives us a
 *     ``getContext('2d')`` — useful in tests),
 *   * a :class:`TimelineSceneGraph` (the registered layers),
 *   * the current :type:`TimelineCamera` + :type:`TimelineViewport`
 *     state,
 *   * the current dataset (rows + segments),
 *   * a :class:`TimelineScheduler` that owns rAF orchestration,
 *   * a :class:`TimelineRendererMetrics` for observability.
 *
 * The renderer is *framework-free* TypeScript so it can run in a
 * worker thread later. React-side glue lives in
 * :func:`useTimelineRenderer`.
 */

import { prepareFrame, resizeCanvasToViewport } from "@/dashboard/timeline/utils/canvas";
import {
  DEFAULT_TIMELINE_PALETTE,
  type TimelineColorPalette,
} from "@/dashboard/timeline/rendering/TimelineColors";
import { TimelineSceneGraph } from "@/dashboard/timeline/rendering/TimelineSceneGraph";
import type {
  RenderContext,
  TimelineLayer,
  TimelineRenderSegment,
  TimelineRow,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { TimelineCamera } from "@/dashboard/timeline/viewport/TimelineCamera";
import {
  EMPTY_VIEWPORT,
  type TimelineViewport,
} from "@/dashboard/timeline/viewport/TimelineViewport";
import {
  TimelineScheduler,
  type SchedulerOptions,
  type DirtyReason,
} from "@/dashboard/timeline/scheduler/TimelineScheduler";
import {
  getTimelineRendererMetrics,
  type TimelineRendererMetrics,
} from "@/dashboard/timeline/observability/timelineRendererMetrics";
import { recordRendererTrace } from "@/dashboard/timeline/diagnostics/trace";

export interface TimelineDataset {
  rows: readonly TimelineRow[];
  segments: readonly TimelineRenderSegment[];
}

export const EMPTY_DATASET: TimelineDataset = { rows: [], segments: [] };

export interface TimelineRendererOptions {
  scheduler?: SchedulerOptions;
  palette?: TimelineColorPalette;
  metrics?: TimelineRendererMetrics;
}

/**
 * Narrow interface the renderer expects from any virtualizer plugged
 * in via :meth:`setVirtualizer`. The full
 * :class:`TimelineVirtualizationEngine` satisfies this — the indirection
 * keeps the rendering module free of a virtualization dependency.
 */
export interface RendererVirtualizer {
  resolveFrame(args: {
    coords: TimelineCoordinateSystem;
    inputs: {
      rows: readonly TimelineRow[];
      segments: readonly TimelineRenderSegment[];
      sequence: number;
    };
  }): {
    rows: readonly TimelineRow[];
    segments: readonly TimelineRenderSegment[];
  };
}

interface CulledSegment extends TimelineRenderSegment {
  __span: { x0: number; width: number; y: number };
}

export class TimelineRenderer {
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private viewport: TimelineViewport = EMPTY_VIEWPORT;
  private camera: TimelineCamera = {
    timeStart: 0,
    timeEnd: 1,
    rowStart: 0,
    rowHeight: 18,
  };
  private dataset: TimelineDataset = EMPTY_DATASET;
  private selectedTaskId: string | null = null;
  private cursorTimeSeconds: number | null = null;
  private palette: TimelineColorPalette;
  private metrics: TimelineRendererMetrics;
  private scheduler: TimelineScheduler;
  private sceneGraph = new TimelineSceneGraph();
  private framesRendered = 0;
  private disposed = false;
  private datasetSequence = 0;
  private virtualizer: RendererVirtualizer | null = null;

  constructor(options: TimelineRendererOptions = {}) {
    this.palette = options.palette ?? DEFAULT_TIMELINE_PALETTE;
    this.metrics = options.metrics ?? getTimelineRendererMetrics();
    this.scheduler = new TimelineScheduler(this.renderFrame, options.scheduler);
  }

  // ── Mount / unmount ────────────────────────────────────────────────

  attachCanvas(canvas: HTMLCanvasElement | null): void {
    this.canvas = canvas;
    this.ctx = canvas ? canvas.getContext("2d") : null;
    if (canvas !== null) {
      this.invalidate("viewport");
    }
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.scheduler.dispose();
    this.canvas = null;
    this.ctx = null;
  }

  // ── Scene graph ────────────────────────────────────────────────────

  addLayer(layer: TimelineLayer): void {
    this.sceneGraph.addLayer(layer);
    this.invalidate("data");
  }

  removeLayer(id: string): void {
    this.sceneGraph.removeLayer(id);
    this.invalidate("data");
  }

  setLayerEnabled(id: string, enabled: boolean): void {
    this.sceneGraph.setLayerEnabled(id, enabled);
    this.invalidate("data");
  }

  layerIds(): readonly string[] {
    return this.sceneGraph.layerIds();
  }

  // ── State updates ──────────────────────────────────────────────────

  setViewport(viewport: TimelineViewport): void {
    this.viewport = viewport;
    if (this.canvas !== null) {
      resizeCanvasToViewport(this.canvas, viewport);
    }
    this.invalidate("viewport");
  }

  setCamera(camera: TimelineCamera): void {
    this.camera = camera;
    this.invalidate("camera");
  }

  setDataset(dataset: TimelineDataset): void {
    this.dataset = dataset;
    this.datasetSequence += 1;
    this.invalidate("data");
  }

  /** Attach (or detach with ``null``) a virtualization engine. When
   *  attached, the renderer delegates culling to it instead of the
   *  inline fast-path. */
  setVirtualizer(virtualizer: RendererVirtualizer | null): void {
    this.virtualizer = virtualizer;
    this.invalidate("data");
  }

  /** Monotonic counter incremented on every ``setDataset`` call —
   *  exposed so external caches (virtualization, hit-test indices) can
   *  detect dataset changes without diffing the array. */
  currentDatasetSequence(): number {
    return this.datasetSequence;
  }

  setSelectedTaskId(taskId: string | null): void {
    this.selectedTaskId = taskId;
    this.invalidate("selection");
  }

  setCursorTimeSeconds(seconds: number | null): void {
    this.cursorTimeSeconds = seconds;
    this.invalidate("overlay");
  }

  setPalette(palette: TimelineColorPalette): void {
    this.palette = palette;
    this.invalidate("data");
  }

  // ── Render control ────────────────────────────────────────────────

  invalidate(reason: DirtyReason = "manual"): void {
    if (this.disposed) return;
    this.metrics.recordInvalidation(reason);
    this.scheduler.invalidate(reason);
  }

  /** Synchronously render now. Used in tests + after attaching. */
  forceRender(): void {
    if (this.disposed) return;
    this.scheduler.forceRender();
  }

  schedulerMetrics() {
    return this.scheduler.metrics();
  }

  rendererMetrics(): TimelineRendererMetrics {
    return this.metrics;
  }

  // ── Internals ──────────────────────────────────────────────────────

  private renderFrame = (): void => {
    if (this.disposed) return;
    if (this.ctx === null || this.canvas === null) return;
    if (this.viewport.cssWidth <= 0 || this.viewport.cssHeight <= 0) return;

    const frameStartMs = typeof performance !== "undefined" ? performance.now() : Date.now();

    const coords = new TimelineCoordinateSystem(this.camera, this.viewport);
    let visibleRows: readonly TimelineRow[];
    let visibleSegments: readonly TimelineRenderSegment[];
    if (this.virtualizer !== null) {
      const frame = this.virtualizer.resolveFrame({
        coords,
        inputs: {
          rows: this.dataset.rows,
          segments: this.dataset.segments,
          sequence: this.datasetSequence,
        },
      });
      visibleRows = frame.rows;
      visibleSegments = this.attachSpans(coords, frame.segments);
    } else {
      const visibleRowRange = coords.visibleRowRange(this.dataset.rows.length);
      const inlineRows: TimelineRow[] = [];
      for (let i = visibleRowRange.startIndex; i < visibleRowRange.endIndex; i += 1) {
        const row = this.dataset.rows[i];
        if (row !== undefined) inlineRows.push(row);
      }
      visibleRows = inlineRows;
      visibleSegments = this.cullSegments(coords, visibleRowRange);
    }

    prepareFrame(this.ctx, this.viewport);
    const context: RenderContext = {
      ctx: this.ctx,
      coords,
      palette: this.palette,
      scene: {
        totalRows: this.dataset.rows.length,
        rows: visibleRows,
        segments: visibleSegments,
        selectedTaskId: this.selectedTaskId,
        cursorTimeSeconds: this.cursorTimeSeconds,
      },
      frameStartMs,
    };

    this.sceneGraph.renderAll(context);
    this.framesRendered += 1;

    const frameEndMs = typeof performance !== "undefined" ? performance.now() : Date.now();
    this.metrics.recordFrame({
      durationMs: frameEndMs - frameStartMs,
      visibleRowCount: visibleRows.length,
      visibleSegmentCount: visibleSegments.length,
    });
    recordRendererTrace({
      kind: "frame",
      detail: `rows=${visibleRows.length} segs=${visibleSegments.length} ms=${(frameEndMs - frameStartMs).toFixed(2)}`,
    });
  };

  private cullSegments(
    coords: TimelineCoordinateSystem,
    range: { startIndex: number; endIndex: number },
  ): CulledSegment[] {
    const out: CulledSegment[] = [];
    for (const segment of this.dataset.segments) {
      if (segment.rowIndex < range.startIndex || segment.rowIndex >= range.endIndex) continue;
      const span = coords.segmentSpan(segment.startSeconds, segment.endSeconds);
      if (span === null) continue;
      const y = coords.rowToY(segment.rowIndex);
      // Squash the span into the segment object so layers don't re-do
      // the world→screen math. Cast through unknown — the field is
      // intentionally opaque to TypeScript's structural typing.
      const culled = {
        ...segment,
        __span: { x0: span.x0, width: span.width, y },
      } as CulledSegment;
      out.push(culled);
    }
    return out;
  }

  /** Attach the legacy ``__span`` field to virtualizer-supplied
   *  segments so the legacy :class:`SegmentLayer` keeps painting
   *  correctly when both layers are present. The canonical
   *  :class:`TimelineSegmentRenderer` ignores ``__span``. */
  private attachSpans(
    coords: TimelineCoordinateSystem,
    segments: readonly TimelineRenderSegment[],
  ): TimelineRenderSegment[] {
    const out: TimelineRenderSegment[] = [];
    for (const segment of segments) {
      const span = coords.segmentSpan(segment.startSeconds, segment.endSeconds);
      if (span === null) {
        out.push(segment);
        continue;
      }
      const y = coords.rowToY(segment.rowIndex);
      const augmented = {
        ...segment,
        __span: { x0: span.x0, width: span.width, y },
      } as CulledSegment;
      out.push(augmented);
    }
    return out;
  }

  // Test seams.

  /** Snapshot used by tests to confirm renderFrame ran. */
  internalState(): {
    framesRendered: number;
    viewport: TimelineViewport;
    camera: TimelineCamera;
  } {
    return {
      framesRendered: this.framesRendered,
      viewport: this.viewport,
      camera: this.camera,
    };
  }
}
