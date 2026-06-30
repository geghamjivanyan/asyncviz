/**
 * Pure viewport-window math.
 *
 * Resolves a :type:`TimelineViewportWindowSnapshot` for the current
 * camera + viewport + overscan, then caches the result on a small
 * single-slot snapshot field so back-to-back resolutions return the
 * same reference when nothing changed.
 *
 * The class is intentionally framework-free so it runs on a worker
 * thread later.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type {
  OverscanConfig,
  TimelineRowWindow,
  TimelineTimeWindow,
  TimelineViewportWindowSnapshot,
} from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";
import { DEFAULT_OVERSCAN } from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";

export interface ViewportWindowOptions {
  overscan?: Partial<OverscanConfig>;
}

export class TimelineViewportWindow {
  private overscan: OverscanConfig;
  private last: TimelineViewportWindowSnapshot | null = null;
  private _resolutions = 0;
  private _hits = 0;

  constructor(options: ViewportWindowOptions = {}) {
    this.overscan = {
      rowOverscan: Math.max(
        0,
        Math.floor(options.overscan?.rowOverscan ?? DEFAULT_OVERSCAN.rowOverscan),
      ),
      timeOverscanSeconds: Math.max(
        0,
        options.overscan?.timeOverscanSeconds ?? DEFAULT_OVERSCAN.timeOverscanSeconds,
      ),
    };
  }

  setOverscan(overscan: Partial<OverscanConfig>): void {
    const next: OverscanConfig = {
      rowOverscan: Math.max(0, Math.floor(overscan.rowOverscan ?? this.overscan.rowOverscan)),
      timeOverscanSeconds: Math.max(
        0,
        overscan.timeOverscanSeconds ?? this.overscan.timeOverscanSeconds,
      ),
    };
    if (
      next.rowOverscan !== this.overscan.rowOverscan ||
      next.timeOverscanSeconds !== this.overscan.timeOverscanSeconds
    ) {
      this.overscan = next;
      this.last = null;
    }
  }

  currentOverscan(): OverscanConfig {
    return this.overscan;
  }

  /** Resolve the viewport window for the given coordinate system +
   *  dataset sequence. Returns the cached snapshot when the inputs are
   *  identical to the previous call. */
  resolve(
    coords: TimelineCoordinateSystem,
    totalRows: number,
    sequence: number,
  ): TimelineViewportWindowSnapshot {
    this._resolutions += 1;
    const key = makeKey(coords, totalRows, sequence, this.overscan);
    if (this.last !== null && this.last.key === key) {
      this._hits += 1;
      return this.last;
    }
    const rows = resolveRowWindow(coords, totalRows, this.overscan.rowOverscan);
    const time = resolveTimeWindow(coords, this.overscan.timeOverscanSeconds);
    const snapshot: TimelineViewportWindowSnapshot = {
      rows,
      time,
      key,
      resolvedAtMs: typeof performance !== "undefined" ? performance.now() : Date.now(),
    };
    this.last = snapshot;
    return snapshot;
  }

  /** Force-invalidate the cached snapshot — used when a downstream
   *  consumer knows the dataset changed mid-frame. */
  invalidate(): void {
    this.last = null;
  }

  peek(): TimelineViewportWindowSnapshot | null {
    return this.last;
  }

  metrics(): { resolutions: number; hits: number } {
    return { resolutions: this._resolutions, hits: this._hits };
  }
}

function resolveRowWindow(
  coords: TimelineCoordinateSystem,
  totalRows: number,
  rowOverscan: number,
): TimelineRowWindow {
  const baseRange = coords.visibleRowRange(totalRows);
  const overscanStartIndex = Math.max(0, baseRange.startIndex - rowOverscan);
  const overscanEndIndex = Math.min(totalRows, baseRange.endIndex + rowOverscan);
  return {
    startIndex: baseRange.startIndex,
    endIndex: baseRange.endIndex,
    overscanStartIndex,
    overscanEndIndex,
    totalRows,
  };
}

function resolveTimeWindow(
  coords: TimelineCoordinateSystem,
  timeOverscanSeconds: number,
): TimelineTimeWindow {
  return {
    startSeconds: coords.camera.timeStart,
    endSeconds: coords.camera.timeEnd,
    overscanStartSeconds: coords.camera.timeStart - timeOverscanSeconds,
    overscanEndSeconds: coords.camera.timeEnd + timeOverscanSeconds,
  };
}

function makeKey(
  coords: TimelineCoordinateSystem,
  totalRows: number,
  sequence: number,
  overscan: OverscanConfig,
): string {
  return [
    coords.camera.timeStart,
    coords.camera.timeEnd,
    coords.camera.rowStart,
    coords.camera.rowHeight,
    coords.viewport.cssWidth,
    coords.viewport.cssHeight,
    coords.viewport.devicePixelRatio,
    totalRows,
    sequence,
    overscan.rowOverscan,
    overscan.timeOverscanSeconds,
  ].join("|");
}
