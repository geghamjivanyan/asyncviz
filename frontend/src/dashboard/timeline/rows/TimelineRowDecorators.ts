/**
 * Row decorator registry.
 *
 * A decorator is a tiny pluggable painter that runs after the row
 * background + label + warning chip. Today only the lineage caret +
 * state pill ship as built-ins, but the registry exists so future
 * profiler/debugger overlays slot in without modifying the canonical
 * row renderer.
 *
 * Decorators are framework-free, deterministic, and rendered in
 * registration order. Each receives the same context the row
 * renderer assembled — they never re-read the store.
 */

import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";
import type { TimelineRowLayoutSnapshot } from "@/dashboard/timeline/rows/TimelineRowLayout";
import { rowStateIndicator } from "@/dashboard/timeline/rows/TimelineRowColors";

export interface RowDecoratorContext {
  ctx: CanvasRenderingContext2D;
  palette: TimelineColorPalette;
  layout: TimelineRowLayoutSnapshot;
  rowTopY: number;
  viewportWidth: number;
  row: TimelineRowProjectionEntry;
}

export interface RowDecorator {
  readonly id: string;
  render(context: RowDecoratorContext): void;
}

/** Lineage caret — small left-aligned glyph showing depth. Renders
 *  only when the row has a parent + the row height has space. */
export const lineageCaretDecorator: RowDecorator = {
  id: "lineage-caret",
  render({ ctx, palette, layout, rowTopY, row }) {
    if (row.depth <= 0) return;
    if (layout.rowHeightPx < 16) return;
    const indent = Math.min(layout.maxIndentPx, row.depth * layout.indentPerDepthPx);
    const x = Math.max(2, indent - 6);
    const y = rowTopY + layout.rowHeightPx / 2;
    ctx.save();
    ctx.strokeStyle = palette.subtle;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y - 3);
    ctx.lineTo(x + 4, y);
    ctx.lineTo(x, y + 3);
    ctx.stroke();
    ctx.restore();
  },
};

/** Leading-edge state indicator — 2-px tall bar in the row's color. */
export const stateIndicatorDecorator: RowDecorator = {
  id: "state-indicator",
  render({ ctx, palette, rowTopY, layout, row }) {
    const heightPx = Math.max(2, layout.rowHeightPx - 6);
    const y = rowTopY + (layout.rowHeightPx - heightPx) / 2;
    ctx.fillStyle = rowStateIndicator(palette, row.state);
    ctx.fillRect(0, y, 2, heightPx);
  },
};

export class RowDecoratorRegistry {
  private decorators: RowDecorator[] = [];

  constructor(initial: readonly RowDecorator[] = []) {
    for (const decorator of initial) this.register(decorator);
  }

  register(decorator: RowDecorator): void {
    if (this.decorators.some((d) => d.id === decorator.id)) {
      throw new Error(`Decorator "${decorator.id}" already registered`);
    }
    this.decorators.push(decorator);
  }

  unregister(id: string): void {
    this.decorators = this.decorators.filter((d) => d.id !== id);
  }

  ids(): readonly string[] {
    return this.decorators.map((d) => d.id);
  }

  render(context: RowDecoratorContext): void {
    for (const decorator of this.decorators) decorator.render(context);
  }
}

/** Convenience: registry preloaded with built-in decorators. */
export function defaultRowDecorators(): RowDecoratorRegistry {
  return new RowDecoratorRegistry([stateIndicatorDecorator, lineageCaretDecorator]);
}
