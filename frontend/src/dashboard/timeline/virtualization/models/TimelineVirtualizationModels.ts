/**
 * Types for the canonical timeline virtualization engine.
 *
 * The engine deals in two strict windows:
 *
 *   * a *strict* visible window — the rows + time range the camera
 *     covers exactly,
 *   * an *overscan* window — strict ± buffer rows / seconds, so
 *     scroll / zoom keep prefetched data on hand and never paint a
 *     blank gutter mid-gesture.
 *
 * Both windows are pure data; the engine recomputes them on demand
 * and caches the result keyed by ``(camera, viewport, dataset
 * sequence)``.
 */

export interface TimelineRowWindow {
  /** First strictly-visible row index. */
  startIndex: number;
  /** Exclusive upper bound for strictly-visible rows. */
  endIndex: number;
  /** First overscan-included row index. */
  overscanStartIndex: number;
  /** Exclusive upper bound for overscan rows. */
  overscanEndIndex: number;
  /** Total rows in the dataset at the time the window was built. */
  totalRows: number;
}

export interface TimelineTimeWindow {
  /** Strict left edge of the visible time window (seconds). */
  startSeconds: number;
  /** Strict right edge of the visible time window (seconds). */
  endSeconds: number;
  /** Overscan-padded left edge (seconds). */
  overscanStartSeconds: number;
  /** Overscan-padded right edge (seconds). */
  overscanEndSeconds: number;
}

/** A unified viewport window — both axes resolved together. */
export interface TimelineViewportWindowSnapshot {
  rows: TimelineRowWindow;
  time: TimelineTimeWindow;
  /** Cache key derived from camera + viewport + dataset sequence —
   *  consumers compare these for ``===``. */
  key: string;
  /** Monotonic ms when the window was resolved. */
  resolvedAtMs: number;
}

/** Configuration of overscan padding. */
export interface OverscanConfig {
  rowOverscan: number;
  timeOverscanSeconds: number;
}

export const DEFAULT_OVERSCAN: OverscanConfig = Object.freeze({
  rowOverscan: 4,
  timeOverscanSeconds: 0,
});

/** Result of the engine's per-frame culling pass. */
export interface VirtualizationFrame<TRow, TSegment> {
  window: TimelineViewportWindowSnapshot;
  rows: readonly TRow[];
  segments: readonly TSegment[];
  /** Total rows considered (after cache lookup or full cull). */
  rowsConsidered: number;
  /** Total segments considered. */
  segmentsConsidered: number;
  /** ``true`` when the frame was served from cache. */
  fromCache: boolean;
}

export interface VirtualizationInputs<TRow, TSegment> {
  rows: readonly TRow[];
  segments: readonly TSegment[];
  /** Sequence cursor — invalidates the cache when it advances. */
  sequence: number;
}
