/**
 * Cursor / overlay layer.
 *
 * Renders the hover cursor as a thin vertical line + caption. Drawn
 * last so it stays visible on top of every other layer.
 */

import type { RenderContext, TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";

export interface OverlayLayerOptions {
  id?: string;
  order?: number;
  enabled?: boolean;
}

export class OverlayLayer implements TimelineLayer {
  readonly id: string;
  readonly order: number;
  enabled: boolean;

  constructor(options: OverlayLayerOptions = {}) {
    this.id = options.id ?? "overlay";
    this.order = options.order ?? 30;
    this.enabled = options.enabled ?? true;
  }

  render({ ctx, coords, palette, scene }: RenderContext): void {
    if (scene.cursorTimeSeconds === null) return;
    const x = Math.round(coords.timeToX(scene.cursorTimeSeconds)) + 0.5;
    if (x < 0 || x > coords.viewport.cssWidth) return;
    ctx.strokeStyle = palette.overlayCursor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, coords.viewport.cssHeight);
    ctx.stroke();
  }
}
