/**
 * Highlights the currently selected row across the full viewport.
 *
 * Painted after the segment layer so the highlight covers the row's
 * background but not the cursor overlay.
 */

import type { RenderContext, TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";

export interface SelectionLayerOptions {
  id?: string;
  order?: number;
  enabled?: boolean;
}

export class SelectionLayer implements TimelineLayer {
  readonly id: string;
  readonly order: number;
  enabled: boolean;

  constructor(options: SelectionLayerOptions = {}) {
    this.id = options.id ?? "selection";
    this.order = options.order ?? 20;
    this.enabled = options.enabled ?? true;
  }

  render({ ctx, coords, palette, scene }: RenderContext): void {
    if (scene.selectedTaskId === null) return;
    const row = scene.rows.find((r) => r.taskId === scene.selectedTaskId);
    if (row === undefined) return;
    const y = coords.rowToY(row.rowIndex);
    const height = coords.camera.rowHeight;
    ctx.fillStyle = palette.selectionFill;
    ctx.fillRect(0, y, coords.viewport.cssWidth, height);
    ctx.strokeStyle = palette.selectionStroke;
    ctx.lineWidth = 1;
    ctx.strokeRect(
      0.5,
      Math.round(y) + 0.5,
      coords.viewport.cssWidth - 1,
      Math.max(1, Math.round(height) - 1),
    );
  }
}
