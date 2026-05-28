/**
 * Decorator registry for segment rendering.
 *
 * Decorators run after the base fill + texture but before the
 * warning + selection overlays. They paint state-specific markers
 * (cancelled strike, failed border, etc.) and are the future home
 * for profiler / debugger overlays.
 *
 * Decorators are framework-free, deterministic, and rendered in
 * registration order. Each receives the same screen rect the
 * renderer already computed — no recomputation.
 */

import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import type { TimelineSegmentProjectionEntry } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";
import type { SegmentScreenRect } from "@/dashboard/timeline/segments/TimelineSegmentGeometry";
import type { SegmentStyle } from "@/dashboard/timeline/segments/TimelineSegmentStyling";
import {
  cancelStrikeColor,
  failedBorderColor,
} from "@/dashboard/timeline/segments/TimelineSegmentStyling";

export interface SegmentDecoratorContext {
  ctx: CanvasRenderingContext2D;
  palette: TimelineColorPalette;
  entry: TimelineSegmentProjectionEntry;
  rect: SegmentScreenRect;
  style: SegmentStyle;
}

export interface SegmentDecorator {
  readonly id: string;
  render(context: SegmentDecoratorContext): void;
}

/** Diagonal strike-through for cancelled segments. */
export const cancelledStrikeDecorator: SegmentDecorator = {
  id: "cancelled-strike",
  render({ ctx, palette, rect, style }) {
    if (!style.cancelledStrike) return;
    if (rect.width <= 1 || rect.height <= 1) return;
    ctx.save();
    ctx.strokeStyle = cancelStrikeColor(palette);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(rect.x, rect.y + rect.height);
    ctx.lineTo(rect.x + rect.width, rect.y);
    ctx.stroke();
    ctx.restore();
  },
};

/** Inset danger border for failed segments. */
export const failedBorderDecorator: SegmentDecorator = {
  id: "failed-border",
  render({ ctx, palette, rect, style }) {
    if (!style.failedBorder) return;
    if (rect.width < 2 || rect.height < 2) return;
    ctx.save();
    ctx.strokeStyle = failedBorderColor(palette);
    ctx.lineWidth = 1.5;
    ctx.strokeRect(rect.x + 0.75, rect.y + 0.75, rect.width - 1.5, rect.height - 1.5);
    ctx.restore();
  },
};

export class SegmentDecoratorRegistry {
  private decorators: SegmentDecorator[] = [];

  constructor(initial: readonly SegmentDecorator[] = []) {
    for (const decorator of initial) this.register(decorator);
  }

  register(decorator: SegmentDecorator): void {
    if (this.decorators.some((d) => d.id === decorator.id)) {
      throw new Error(`Segment decorator "${decorator.id}" already registered`);
    }
    this.decorators.push(decorator);
  }

  unregister(id: string): void {
    this.decorators = this.decorators.filter((d) => d.id !== id);
  }

  ids(): readonly string[] {
    return this.decorators.map((d) => d.id);
  }

  render(context: SegmentDecoratorContext): void {
    for (const decorator of this.decorators) decorator.render(context);
  }
}

export function defaultSegmentDecorators(): SegmentDecoratorRegistry {
  return new SegmentDecoratorRegistry([cancelledStrikeDecorator, failedBorderDecorator]);
}
