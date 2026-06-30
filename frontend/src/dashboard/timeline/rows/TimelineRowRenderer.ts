/**
 * Canonical task-timeline row renderer.
 *
 * The row renderer is a *controller* that owns two complementary
 * :type:`TimelineLayer` passes:
 *
 *   * a **background** pass — order ``5``, drawn behind segments. It
 *     paints row backgrounds, state pills, lineage carets, and warning
 *     tints. Segments later draw on top of these tints in the timeline
 *     column.
 *   * a **foreground** pass — order ``25``, drawn over segments and the
 *     base selection layer. It paints the opaque label column, label
 *     text, warning chips, and the selection / replay highlight band.
 *
 * Splitting the work in two passes keeps the canvas correct (segments
 * cannot leak into the label column, but their backing tints stay
 * visible behind them), and keeps the row renderer scalable — the
 * label-foreground pass can skip whole rows when the label column is
 * collapsed.
 *
 * The renderer is framework-free TypeScript so it runs on a worker
 * thread later. Rich row metadata flows in via :type:`TimelineRow`
 * fields populated by :func:`projectTimeline`.
 */

import type { RenderContext, TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";
import { rowBackgroundFill, rowSeparatorStroke } from "@/dashboard/timeline/rows/TimelineRowColors";
import {
  TimelineRowLayout,
  type TimelineRowLayoutOptions,
} from "@/dashboard/timeline/rows/TimelineRowLayout";
import { TimelineRowLabelRenderer } from "@/dashboard/timeline/rows/TimelineRowLabels";
import { renderRowWarnings } from "@/dashboard/timeline/rows/TimelineRowWarnings";
import { renderRowSelection } from "@/dashboard/timeline/rows/TimelineRowSelection";
import {
  defaultRowDecorators,
  type RowDecoratorRegistry,
} from "@/dashboard/timeline/rows/TimelineRowDecorators";
import { normalizeRow } from "@/dashboard/timeline/rows/utils/normalizeRow";
import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";
import {
  getTimelineRowMetrics,
  type TimelineRowMetrics,
} from "@/dashboard/timeline/rows/TimelineRowMetrics";
import { recordRowTrace } from "@/dashboard/timeline/rows/diagnostics/rowTrace";

export interface TimelineRowRendererOptions {
  /** Override background-layer id. */
  backgroundId?: string;
  /** Override foreground-layer id. */
  foregroundId?: string;
  /** Background-layer order (default ``5``). */
  backgroundOrder?: number;
  /** Foreground-layer order (default ``25``). */
  foregroundOrder?: number;
  /** Initial enabled flag, applied to both passes. */
  enabled?: boolean;
  layout?: TimelineRowLayout | TimelineRowLayoutOptions;
  labelRenderer?: TimelineRowLabelRenderer;
  decorators?: RowDecoratorRegistry;
  metrics?: TimelineRowMetrics;
}

class RowBackgroundLayer implements TimelineLayer {
  readonly id: string;
  readonly order: number;
  enabled = true;
  constructor(
    id: string,
    order: number,
    enabled: boolean,
    private readonly host: TimelineRowRenderer,
  ) {
    this.id = id;
    this.order = order;
    this.enabled = enabled;
  }
  render(context: RenderContext): void {
    this.host.renderBackgrounds(context);
  }
}

class RowForegroundLayer implements TimelineLayer {
  readonly id: string;
  readonly order: number;
  enabled = true;
  constructor(
    id: string,
    order: number,
    enabled: boolean,
    private readonly host: TimelineRowRenderer,
  ) {
    this.id = id;
    this.order = order;
    this.enabled = enabled;
  }
  render(context: RenderContext): void {
    this.host.renderForeground(context);
  }
}

export class TimelineRowRenderer {
  readonly background: TimelineLayer;
  readonly foreground: TimelineLayer;

  private readonly layout: TimelineRowLayout;
  private readonly labelRenderer: TimelineRowLabelRenderer;
  private readonly decorators: RowDecoratorRegistry;
  private readonly metrics: TimelineRowMetrics;

  constructor(options: TimelineRowRendererOptions = {}) {
    this.layout =
      options.layout instanceof TimelineRowLayout
        ? options.layout
        : new TimelineRowLayout(options.layout);
    this.metrics = options.metrics ?? getTimelineRowMetrics();
    this.labelRenderer =
      options.labelRenderer ?? new TimelineRowLabelRenderer({ metrics: this.metrics });
    this.decorators = options.decorators ?? defaultRowDecorators();
    const enabled = options.enabled ?? true;
    this.background = new RowBackgroundLayer(
      options.backgroundId ?? "rows-background",
      options.backgroundOrder ?? 5,
      enabled,
      this,
    );
    this.foreground = new RowForegroundLayer(
      options.foregroundId ?? "rows-foreground",
      options.foregroundOrder ?? 25,
      enabled,
      this,
    );
  }

  /** Convenience for callers that consume the renderer as one layer. */
  get layers(): readonly TimelineLayer[] {
    return [this.background, this.foreground];
  }

  /** Toggle both passes at once. */
  setEnabled(value: boolean): void {
    this.background.enabled = value;
    this.foreground.enabled = value;
  }

  getLayout(): TimelineRowLayout {
    return this.layout;
  }

  getLabelRenderer(): TimelineRowLabelRenderer {
    return this.labelRenderer;
  }

  getDecorators(): RowDecoratorRegistry {
    return this.decorators;
  }

  /** Background pass — backgrounds, decorators, warning tints. */
  renderBackgrounds(context: RenderContext): void {
    const { ctx, coords, palette, scene } = context;
    if (scene.rows.length === 0) return;

    const frameStart = typeof performance !== "undefined" ? performance.now() : Date.now();
    const layoutSnapshot = this.layout.resolve(coords);
    const viewportWidth = coords.viewport.cssWidth;
    const rowStart = coords.camera.rowStart;
    const rowHeight = layoutSnapshot.rowHeightPx;
    let replayMarkedThisFrame = false;
    let visibleRowCount = 0;

    for (const raw of scene.rows) {
      const row = normalizeRow(raw);
      const rowTopY = (row.rowIndex - rowStart) * rowHeight;
      this.paintRowBackground({
        ctx,
        palette,
        layout: layoutSnapshot,
        row,
        rowTopY,
        viewportWidth,
      });
      this.decorators.render({ ctx, palette, layout: layoutSnapshot, rowTopY, viewportWidth, row });
      renderRowWarnings({
        ctx,
        palette,
        layout: layoutSnapshot,
        rowTopY,
        viewportWidth,
        row,
        metrics: this.metrics,
      });
      if (row.replay !== null) replayMarkedThisFrame = true;
      this.metrics.recordRow();
      visibleRowCount += 1;
    }

    const frameEnd = typeof performance !== "undefined" ? performance.now() : Date.now();
    this.metrics.recordFrame({
      durationMs: frameEnd - frameStart,
      visibleRows: visibleRowCount,
      replayMarked: replayMarkedThisFrame,
    });
    recordRowTrace({
      kind: "frame",
      detail: `bg rows=${visibleRowCount} dur=${(frameEnd - frameStart).toFixed(2)}ms`,
    });
  }

  /** Foreground pass — label column fill, labels, selection band. */
  renderForeground(context: RenderContext): void {
    const { ctx, coords, palette, scene } = context;
    if (scene.rows.length === 0) return;

    const layoutSnapshot = this.layout.resolve(coords);
    const viewportWidth = coords.viewport.cssWidth;
    const rowStart = coords.camera.rowStart;
    const rowHeight = layoutSnapshot.rowHeightPx;

    // Opaque label column — covers anything that might have leaked
    // into the left gutter from the segment layer.
    if (layoutSnapshot.labelColumnWidthPx > 0) {
      ctx.fillStyle = palette.canvas;
      ctx.fillRect(0, 0, layoutSnapshot.labelColumnWidthPx, coords.viewport.cssHeight);
      // Column gutter divider.
      ctx.strokeStyle = palette.line;
      ctx.lineWidth = 1;
      ctx.beginPath();
      const dividerX = Math.round(layoutSnapshot.labelColumnWidthPx) + 0.5;
      ctx.moveTo(dividerX, 0);
      ctx.lineTo(dividerX, coords.viewport.cssHeight);
      ctx.stroke();
    }

    for (const raw of scene.rows) {
      const row = normalizeRow(raw);
      const rowTopY = (row.rowIndex - rowStart) * rowHeight;
      renderRowSelection({
        ctx,
        palette,
        layout: layoutSnapshot,
        rowTopY,
        viewportWidth,
        row,
        selected: scene.selectedTaskId !== null && scene.selectedTaskId === row.taskId,
        metrics: this.metrics,
      });
      this.labelRenderer.render({
        ctx,
        palette,
        layout: layoutSnapshot,
        row,
        rowTopY,
      });
    }
  }

  private paintRowBackground(args: {
    ctx: CanvasRenderingContext2D;
    palette: RenderContext["palette"];
    layout: ReturnType<TimelineRowLayout["resolve"]>;
    row: TimelineRowProjectionEntry;
    rowTopY: number;
    viewportWidth: number;
  }): void {
    const { ctx, palette, layout, row, rowTopY, viewportWidth } = args;
    const fill = rowBackgroundFill(palette, row.state);
    if (fill !== "transparent") {
      ctx.fillStyle = fill;
      ctx.fillRect(0, rowTopY, viewportWidth, layout.rowHeightPx);
    }
    ctx.strokeStyle = rowSeparatorStroke(palette);
    ctx.lineWidth = 1;
    ctx.beginPath();
    const sepY = Math.round(rowTopY + layout.rowHeightPx) - 0.5;
    ctx.moveTo(0, sepY);
    ctx.lineTo(viewportWidth, sepY);
    ctx.stroke();
  }
}
