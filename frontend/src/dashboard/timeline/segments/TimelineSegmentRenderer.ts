/**
 * Canonical task-lifecycle segment renderer.
 *
 * The segment renderer is a :type:`TimelineLayer` registered between
 * the row backgrounds (order 5) and the row foreground (order 25).
 * Each frame it:
 *
 *   1. resolves the segment layout for the current viewport,
 *   2. iterates ``scene.segments`` in deterministic order,
 *   3. resolves geometry via the pure projection helper (cached
 *      across frames when the camera + layout fingerprint matches),
 *   4. resolves styling via the pure styling helper,
 *   5. paints fill → texture → decorators → warning → selection /
 *      replay, in that order,
 *   6. emits observability counters via :class:`TimelineSegmentMetrics`.
 *
 * The renderer is framework-free TypeScript so it runs on a worker
 * thread later. Rich segment metadata flows in via
 * :type:`TimelineRenderSegment` fields populated by
 * :func:`projectTimeline`.
 */

import type {
  RenderContext,
  TimelineLayer,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import { defaultSegmentDecorators } from "@/dashboard/timeline/segments/TimelineSegmentDecorators";
import type { SegmentDecoratorRegistry } from "@/dashboard/timeline/segments/TimelineSegmentDecorators";
import {
  TimelineSegmentLayout,
  type TimelineSegmentLayoutOptions,
  type TimelineSegmentLayoutSnapshot,
} from "@/dashboard/timeline/segments/TimelineSegmentLayout";
import type { TimelineRowLayout } from "@/dashboard/timeline/rows/TimelineRowLayout";
import {
  cameraKey,
  layoutKey,
  TimelineSegmentGeometryCache,
} from "@/dashboard/timeline/segments/TimelineSegmentCaching";
import {
  projectSegmentRect,
  type SegmentScreenRect,
} from "@/dashboard/timeline/segments/TimelineSegmentGeometry";
import {
  resolveSegmentStyle,
  type SegmentStyle,
} from "@/dashboard/timeline/segments/TimelineSegmentStyling";
import { renderSegmentWarning } from "@/dashboard/timeline/segments/TimelineSegmentWarnings";
import { renderSegmentSelection } from "@/dashboard/timeline/segments/TimelineSegmentSelection";
import { TimelineSegmentTextureCache } from "@/dashboard/timeline/segments/TimelineSegmentTextures";
import {
  getTimelineSegmentMetrics,
  type TimelineSegmentMetrics,
} from "@/dashboard/timeline/segments/TimelineSegmentMetrics";
import { normalizeSegment } from "@/dashboard/timeline/segments/utils/normalizeSegment";
import type { TimelineSegmentProjectionEntry } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";
import { recordSegmentTrace } from "@/dashboard/timeline/segments/diagnostics/segmentTrace";

export interface TimelineSegmentRendererOptions {
  id?: string;
  order?: number;
  enabled?: boolean;
  layout?: TimelineSegmentLayout | TimelineSegmentLayoutOptions;
  decorators?: SegmentDecoratorRegistry;
  metrics?: TimelineSegmentMetrics;
  textures?: TimelineSegmentTextureCache;
  geometryCache?: TimelineSegmentGeometryCache;
  /** When set, the renderer reads the timeline column origin / width
   *  from this row layout each frame so segments stay aligned with
   *  the label gutter even as the viewport resizes. */
  rowLayout?: TimelineRowLayout;
}

export class TimelineSegmentRenderer implements TimelineLayer {
  readonly id: string;
  readonly order: number;
  enabled: boolean;

  private readonly layout: TimelineSegmentLayout;
  private readonly decorators: SegmentDecoratorRegistry;
  private readonly metrics: TimelineSegmentMetrics;
  private readonly textures: TimelineSegmentTextureCache;
  private readonly geometryCache: TimelineSegmentGeometryCache;
  private rowLayout: TimelineRowLayout | null;

  constructor(options: TimelineSegmentRendererOptions = {}) {
    this.id = options.id ?? "segments";
    this.order = options.order ?? 10;
    this.enabled = options.enabled ?? true;
    this.layout =
      options.layout instanceof TimelineSegmentLayout
        ? options.layout
        : new TimelineSegmentLayout(options.layout);
    this.decorators = options.decorators ?? defaultSegmentDecorators();
    this.metrics = options.metrics ?? getTimelineSegmentMetrics();
    this.textures = options.textures ?? new TimelineSegmentTextureCache();
    this.geometryCache = options.geometryCache ?? new TimelineSegmentGeometryCache();
    this.rowLayout = options.rowLayout ?? null;
  }

  /** Bind / unbind the row layout the segment column tracks. */
  setRowLayout(rowLayout: TimelineRowLayout | null): void {
    this.rowLayout = rowLayout;
  }

  getLayout(): TimelineSegmentLayout {
    return this.layout;
  }

  getDecorators(): SegmentDecoratorRegistry {
    return this.decorators;
  }

  getMetrics(): TimelineSegmentMetrics {
    return this.metrics;
  }

  /** Allow callers (e.g. the React glue) to update the timeline column
   *  origin/width when the row layout snapshot changes. */
  setTimelineColumn(originX: number, widthPx: number): void {
    this.layout.setColumn(originX, widthPx);
  }

  render(context: RenderContext): void {
    if (!this.enabled) return;
    const { ctx, coords, palette, scene } = context;
    if (scene.segments.length === 0) return;

    const frameStart =
      typeof performance !== "undefined" ? performance.now() : Date.now();

    // Sync the timeline column from the row layout if one is bound,
    // so segments stay aligned with the label gutter on resize.
    if (this.rowLayout !== null) {
      const rowSnapshot = this.rowLayout.resolve(coords);
      this.layout.setColumn(rowSnapshot.timelineColumnX, rowSnapshot.timelineColumnWidthPx);
    }
    const layoutSnapshot = this.layout.resolve(coords);

    // Sync cache epoch — clears stale rects when camera or layout
    // fingerprint changes.
    this.geometryCache.syncEpoch(cameraKey(coords.camera), layoutKey(layoutSnapshot));

    const drawablePass: Array<{
      entry: TimelineSegmentProjectionEntry;
      rect: SegmentScreenRect;
      style: SegmentStyle;
    }> = [];

    let culled = 0;
    let visible = 0;
    let active = 0;
    let replayMarked = false;
    let overlaps = 0;
    let lastRowIndex = -1;
    let lastEndSeconds = -Infinity;

    for (const raw of scene.segments) {
      const entry = normalizeSegment(raw);
      const rect = this.resolveRect(entry, context, layoutSnapshot);
      if (rect === null) {
        culled += 1;
        continue;
      }
      const style = resolveSegmentStyle({
        entry,
        palette,
        selected: scene.selectedTaskId !== null && scene.selectedTaskId === entry.taskId,
      });
      drawablePass.push({ entry, rect, style });
      visible += 1;
      if (entry.isActive) active += 1;
      if (entry.replay !== null) replayMarked = true;

      // Cheap overlap detector — scene segments come in row-major
      // order so we only compare against the previous segment.
      if (entry.rowIndex === lastRowIndex && entry.startSeconds < lastEndSeconds) {
        overlaps += 1;
      }
      lastRowIndex = entry.rowIndex;
      lastEndSeconds = Math.max(lastEndSeconds, entry.endSeconds);
    }

    // Clip painting to the timeline column so segments never leak
    // into the label gutter even when the row foreground is off.
    ctx.save();
    ctx.beginPath();
    ctx.rect(
      layoutSnapshot.timelineColumnX,
      0,
      layoutSnapshot.timelineColumnWidthPx,
      coords.viewport.cssHeight,
    );
    ctx.clip();

    for (const { entry, rect, style } of drawablePass) {
      this.paintSegment(ctx, palette, entry, rect, style);
      this.metrics.recordSegment();
    }

    ctx.restore();

    // Cache stats → metrics + reset for next frame's accounting.
    this.metrics.recordGeometry({
      hits: this.geometryCache.hits(),
      misses: this.geometryCache.misses(),
      evictions: this.geometryCache.evictions(),
    });

    const frameEnd =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    this.metrics.recordFrame({
      durationMs: frameEnd - frameStart,
      visibleSegments: visible,
      culled,
      overlaps,
      replayMarked,
      activeSegments: active,
    });
    recordSegmentTrace({
      kind: "frame",
      detail: `visible=${visible} culled=${culled} overlaps=${overlaps} dur=${(
        frameEnd - frameStart
      ).toFixed(2)}ms`,
    });
  }

  private resolveRect(
    entry: TimelineSegmentProjectionEntry,
    context: RenderContext,
    layout: TimelineSegmentLayoutSnapshot,
  ): SegmentScreenRect | null {
    const cached = this.geometryCache.get(entry.segmentId);
    if (cached !== null) return cached;
    const rect = projectSegmentRect({
      segment: entry,
      coords: context.coords,
      layout,
    });
    if (rect === null) return null;
    this.geometryCache.set(entry.segmentId, rect);
    return rect;
  }

  private paintSegment(
    ctx: CanvasRenderingContext2D,
    palette: RenderContext["palette"],
    entry: TimelineSegmentProjectionEntry,
    rect: SegmentScreenRect,
    style: SegmentStyle,
  ): void {
    // Base fill.
    ctx.fillStyle = style.fill;
    ctx.fillRect(rect.x, rect.y, rect.width, rect.height);

    // Texture overlay — pattern fill stacked on top of base color.
    if (style.texture !== "none") {
      const pattern =
        style.texture === "hatch"
          ? this.textures.hatch(ctx, style.textureColor)
          : this.textures.dots(ctx, style.textureColor);
      if (pattern !== null) {
        ctx.save();
        ctx.fillStyle = pattern;
        ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
        ctx.restore();
      }
    }

    // Decorators (cancelled strike, failed border, future profiler
    // overlays).
    this.decorators.render({
      ctx,
      palette,
      entry,
      rect,
      style,
    });
    this.metrics.recordDecorator();

    // Active glow stroke — drawn before warning/selection so they sit
    // on top.
    if (style.stroke !== null && rect.width > 0 && rect.height > 0) {
      ctx.save();
      ctx.strokeStyle = style.stroke;
      ctx.lineWidth = style.strokeWidth;
      ctx.strokeRect(
        Math.round(rect.x) + 0.5,
        Math.round(rect.y) + 0.5,
        Math.max(0, Math.round(rect.width) - 1),
        Math.max(0, Math.round(rect.height) - 1),
      );
      ctx.restore();
    }

    // Warning ring.
    if (style.warningStroke !== null) {
      renderSegmentWarning({ ctx, rect, color: style.warningStroke });
      this.metrics.recordWarning();
    }

    // Selection / replay overlays.
    if (style.selection !== null || style.replay !== null) {
      renderSegmentSelection({
        ctx,
        rect,
        selection: style.selection,
        replay: style.replay,
      });
      if (style.selection !== null) this.metrics.recordSelection();
    }
  }
}
