/**
 * Renders the visible timeline segments.
 *
 * The layer reads pre-culled segments from the render scene — the
 * renderer is responsible for culling so the layer can stay
 * single-purpose. Segments are drawn as filled rectangles with a
 * 1-pixel inset so adjacent segments stay distinguishable.
 */

import {
  segmentFill,
  type TimelineColorPalette,
} from "@/dashboard/timeline/rendering/TimelineColors";
import type {
  RenderContext,
  TimelineLayer,
  TimelineRenderSegment,
} from "@/dashboard/timeline/rendering/TimelineLayer";

export interface SegmentLayerOptions {
  id?: string;
  order?: number;
  enabled?: boolean;
  /** Pixel inset applied vertically inside the row. */
  rowPaddingPx?: number;
}

export class SegmentLayer implements TimelineLayer {
  readonly id: string;
  readonly order: number;
  enabled: boolean;
  private padding: number;

  constructor(options: SegmentLayerOptions = {}) {
    this.id = options.id ?? "segments";
    this.order = options.order ?? 10;
    this.enabled = options.enabled ?? true;
    this.padding = options.rowPaddingPx ?? 2;
  }

  render({ ctx, coords, palette, scene }: RenderContext): void {
    const rowHeight = coords.camera.rowHeight;
    for (const segment of scene.segments) {
      this.renderSegment(ctx, palette, segment, rowHeight);
    }
  }

  private renderSegment(
    ctx: CanvasRenderingContext2D,
    palette: TimelineColorPalette,
    segment: TimelineRenderSegment,
    rowHeight: number,
  ): void {
    // Compute span via the coordinate system — relying on the scene
    // pre-cull, but still doing the screen math here so layers stay
    // independently testable.
    const span = (segment as unknown as { __span?: { x0: number; width: number; y: number } })
      .__span;
    if (span === undefined) return;
    const fill = segmentFill(palette, segment.intent);
    ctx.fillStyle = fill;
    const height = Math.max(1, rowHeight - this.padding * 2);
    ctx.fillRect(span.x0, span.y + this.padding, span.width, height);
    if (segment.isActive) {
      ctx.strokeStyle = palette.accent;
      ctx.lineWidth = 1;
      ctx.strokeRect(
        Math.round(span.x0) + 0.5,
        Math.round(span.y + this.padding) + 0.5,
        Math.max(0, span.width - 1),
        height - 1,
      );
    }
  }
}
