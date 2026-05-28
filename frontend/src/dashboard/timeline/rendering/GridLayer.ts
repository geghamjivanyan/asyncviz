/**
 * Background grid — vertical time ticks + horizontal row separators.
 *
 * The grid renders behind every other layer so segments + selection
 * highlights paint cleanly on top.
 */

import type { RenderContext, TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";
import { pickTickInterval } from "@/dashboard/timeline/utils/ticks";

export interface GridLayerOptions {
  id?: string;
  order?: number;
  enabled?: boolean;
  /** Target tick density in pixels — the time axis aims for ~1 tick / N px. */
  targetTickSpacingPx?: number;
}

export class GridLayer implements TimelineLayer {
  readonly id: string;
  readonly order: number;
  enabled: boolean;
  private targetTickSpacingPx: number;

  constructor(options: GridLayerOptions = {}) {
    this.id = options.id ?? "grid";
    this.order = options.order ?? 0;
    this.enabled = options.enabled ?? true;
    this.targetTickSpacingPx = options.targetTickSpacingPx ?? 80;
  }

  render({ ctx, coords, palette, scene }: RenderContext): void {
    const { viewport, camera } = coords;
    // Background fill.
    ctx.fillStyle = palette.canvas;
    ctx.fillRect(0, 0, viewport.cssWidth, viewport.cssHeight);

    // Horizontal row separators.
    ctx.strokeStyle = palette.gridMinor;
    ctx.lineWidth = 1;
    const visibleRange = coords.visibleRowRange(scene.totalRows);
    ctx.beginPath();
    for (let i = visibleRange.startIndex; i <= visibleRange.endIndex; i += 1) {
      const y = Math.round(coords.rowToY(i)) + 0.5;
      ctx.moveTo(0, y);
      ctx.lineTo(viewport.cssWidth, y);
    }
    ctx.stroke();

    // Vertical time ticks.
    const duration = camera.timeEnd - camera.timeStart;
    if (duration <= 0 || coords.pixelsPerSecond <= 0) return;
    const interval = pickTickInterval(duration, viewport.cssWidth, this.targetTickSpacingPx);
    const firstTick = Math.ceil(camera.timeStart / interval) * interval;
    ctx.strokeStyle = palette.gridMajor;
    ctx.beginPath();
    for (let t = firstTick; t <= camera.timeEnd; t += interval) {
      const x = Math.round(coords.timeToX(t)) + 0.5;
      ctx.moveTo(x, 0);
      ctx.lineTo(x, viewport.cssHeight);
    }
    ctx.stroke();
  }
}
