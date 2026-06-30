/**
 * Viewport culling adapter.
 *
 * The existing :mod:`TimelineCulling` is a pure geometry helper; this
 * adapter layers cache + overscan + stats on top so the optimization
 * layer can drive culling without inflating the renderer.
 *
 * The culler is *coordinate-system aware* — it asks the supplied
 * :class:`TimelineCoordinateSystem` for the visible window and clips
 * caller-supplied items against it. Items are pure values; this
 * module knows nothing about React or the canvas.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

export interface CullableBounds {
  /** World-time start (seconds). */
  readonly startSeconds: number;
  /** World-time end (seconds). */
  readonly endSeconds: number;
  /** Row index the item belongs to. */
  readonly rowIndex: number;
}

export interface ViewportCullingStats {
  readonly itemsConsidered: number;
  readonly itemsCulled: number;
  readonly itemsRetained: number;
  /** Fraction of items removed by culling (0..1). */
  readonly cullRatio: number;
}

export class TimelineViewportCuller {
  private itemsConsidered = 0;
  private itemsCulled = 0;
  private itemsRetained = 0;

  constructor(private readonly overscanPx: number) {}

  /** Cull a list of items against the active coordinate system. The
   *  output array preserves input order. */
  cull<T extends CullableBounds>(coords: TimelineCoordinateSystem, items: readonly T[]): T[] {
    const overscanRows = this.overscanPx / coords.camera.rowHeight;
    const rowStart = coords.camera.rowStart - overscanRows;
    const rowVisible =
      coords.viewport.cssHeight > 0
        ? coords.viewport.cssHeight / coords.camera.rowHeight + overscanRows * 2
        : 0;
    const rowEnd = rowStart + rowVisible;
    const overscanSeconds =
      coords.pixelsPerSecond > 0 ? this.overscanPx / coords.pixelsPerSecond : 0;
    const timeStart = coords.camera.timeStart - overscanSeconds;
    const timeEnd = coords.camera.timeEnd + overscanSeconds;

    const out: T[] = [];
    for (const item of items) {
      this.itemsConsidered += 1;
      if (item.rowIndex + 1 < rowStart || item.rowIndex > rowEnd) {
        this.itemsCulled += 1;
        continue;
      }
      if (item.endSeconds < timeStart || item.startSeconds > timeEnd) {
        this.itemsCulled += 1;
        continue;
      }
      this.itemsRetained += 1;
      out.push(item);
    }
    return out;
  }

  /** Reports whether ``row`` is currently within the visible (+overscan)
   *  band. */
  isRowVisible(coords: TimelineCoordinateSystem, rowIndex: number): boolean {
    const overscanRows = this.overscanPx / coords.camera.rowHeight;
    const rowStart = coords.camera.rowStart - overscanRows;
    const rowVisible =
      coords.viewport.cssHeight > 0
        ? coords.viewport.cssHeight / coords.camera.rowHeight + overscanRows * 2
        : 0;
    const rowEnd = rowStart + rowVisible;
    return rowIndex + 1 >= rowStart && rowIndex <= rowEnd;
  }

  /** Reports whether the world-time span ``[start, end]`` intersects
   *  the visible (+overscan) window. */
  isTimeVisible(coords: TimelineCoordinateSystem, start: number, end: number): boolean {
    const overscanSeconds =
      coords.pixelsPerSecond > 0 ? this.overscanPx / coords.pixelsPerSecond : 0;
    return (
      end >= coords.camera.timeStart - overscanSeconds &&
      start <= coords.camera.timeEnd + overscanSeconds
    );
  }

  stats(): ViewportCullingStats {
    const total = this.itemsConsidered;
    return {
      itemsConsidered: total,
      itemsCulled: this.itemsCulled,
      itemsRetained: this.itemsRetained,
      cullRatio: total > 0 ? this.itemsCulled / total : 0,
    };
  }

  reset(): void {
    this.itemsConsidered = 0;
    this.itemsCulled = 0;
    this.itemsRetained = 0;
  }
}
