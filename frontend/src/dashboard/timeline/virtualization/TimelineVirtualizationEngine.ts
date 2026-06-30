/**
 * Canonical timeline virtualization engine.
 *
 * The engine is the single source of truth for "what is visible right
 * now". It composes:
 *
 *   * :class:`TimelineViewportWindow` — viewport math + window cache,
 *   * :class:`TimelineSegmentWindowing` — spatial index + segment
 *     culling,
 *   * :func:`projectRowWindow` — row slicing,
 *   * :class:`TimelineVirtualizationCache` — viewport-keyed cache of
 *     ``VirtualizationFrame`` results,
 *   * :class:`TimelineWindowMetrics` — observability,
 *   * :class:`TimelineOverscan` — overscan policy.
 *
 * The engine is framework-free TypeScript. React glue lives in
 * :func:`useTimelineVirtualization`.
 *
 * Determinism rules:
 *
 *   * the cache key is the viewport-window key — identical inputs
 *     always return the same frame reference,
 *   * row slicing preserves the projection's stable ordering,
 *   * segment culling is row-major + start-time ascending so replay
 *     frames are byte-identical to live frames.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { TimelineViewportWindow } from "@/dashboard/timeline/virtualization/TimelineViewportWindow";
import { TimelineSegmentWindowing } from "@/dashboard/timeline/virtualization/TimelineSegmentWindowing";
import { projectRowWindow } from "@/dashboard/timeline/virtualization/TimelineRowWindowing";
import { TimelineVirtualizationCache } from "@/dashboard/timeline/virtualization/TimelineVirtualizationCache";
import {
  getTimelineWindowMetrics,
  type TimelineWindowMetrics,
} from "@/dashboard/timeline/virtualization/TimelineWindowMetrics";
import type { CullableRow } from "@/dashboard/timeline/virtualization/TimelineVisibilityCulling";
import type { SpatialIndexable } from "@/dashboard/timeline/virtualization/utils/spatialIndex";
import type {
  OverscanConfig,
  VirtualizationFrame,
  VirtualizationInputs,
} from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";
import {
  traceCacheHit,
  traceCacheMiss,
  traceIndexBuild,
  traceRowCull,
  traceSegmentCull,
  traceVirtualizationInvalidate,
  traceWindowResolve,
} from "@/dashboard/timeline/virtualization/TimelineVirtualizationTracing";

export interface TimelineVirtualizationEngineOptions<
  TRow extends CullableRow,
  TSegment extends SpatialIndexable,
> {
  overscan?: Partial<OverscanConfig>;
  cacheCapacity?: number;
  metrics?: TimelineWindowMetrics;
  /** Override the segment-windowing subsystem (useful for tests). */
  segmentWindowing?: TimelineSegmentWindowing<TSegment>;
  /** Inhibit the spatial index. */
  disableSpatialIndex?: boolean;
  /** Threshold below which the spatial index is skipped. */
  indexMinSegments?: number;
  /** Phantom type guard for ``TRow``. */
  readonly __rowMarker?: TRow;
}

export class TimelineVirtualizationEngine<
  TRow extends CullableRow,
  TSegment extends SpatialIndexable,
> {
  private readonly viewportWindow: TimelineViewportWindow;
  private readonly segmentWindowing: TimelineSegmentWindowing<TSegment>;
  private readonly cache: TimelineVirtualizationCache<TRow, TSegment>;
  private readonly metrics: TimelineWindowMetrics;

  constructor(options: TimelineVirtualizationEngineOptions<TRow, TSegment> = {}) {
    this.viewportWindow = new TimelineViewportWindow({ overscan: options.overscan });
    this.segmentWindowing =
      options.segmentWindowing ??
      new TimelineSegmentWindowing<TSegment>({
        disableIndex: options.disableSpatialIndex,
        indexMinSegments: options.indexMinSegments,
      });
    this.cache = new TimelineVirtualizationCache<TRow, TSegment>(options.cacheCapacity);
    this.metrics = options.metrics ?? getTimelineWindowMetrics();
  }

  // ── public API ───────────────────────────────────────────────────

  /** Resolve the visible rows + segments for the given camera +
   *  viewport + dataset. Caches the frame so back-to-back resolves
   *  with identical inputs are free. */
  resolveFrame(args: {
    coords: TimelineCoordinateSystem;
    inputs: VirtualizationInputs<TRow, TSegment>;
  }): VirtualizationFrame<TRow, TSegment> {
    const { coords, inputs } = args;
    this.cache.syncSequence(inputs.sequence);
    const window = this.viewportWindow.resolve(coords, inputs.rows.length, inputs.sequence);
    const fromWindowCache =
      this.viewportWindow.peek() !== null && this.viewportWindow.metrics().hits > 0;
    this.metrics.recordWindowResolution({ fromCache: fromWindowCache });
    traceWindowResolve(`key=${window.key}`);

    const cached = this.cache.get(window.key);
    if (cached !== null) {
      this.metrics.recordCacheLookup(true);
      traceCacheHit(`key=${window.key}`);
      return cached;
    }
    this.metrics.recordCacheLookup(false);
    traceCacheMiss(`key=${window.key}`);

    const start = typeof performance !== "undefined" ? performance.now() : Date.now();

    const rows = projectRowWindow(inputs.rows, window.rows);
    this.metrics.recordRowCull({ visible: rows.length, total: inputs.rows.length });
    traceRowCull(`visible=${rows.length}/${inputs.rows.length}`);

    const prevIndexBuilds = this.segmentWindowing.metrics().indexBuilds;
    const segments = this.segmentWindowing.resolve({
      segments: inputs.segments,
      sequence: inputs.sequence,
      rowWindow: window.rows,
      timeWindow: window.time,
    });
    const indexBuildDelta = this.segmentWindowing.metrics().indexBuilds - prevIndexBuilds;
    if (indexBuildDelta > 0) {
      this.metrics.recordIndexBuild(indexBuildDelta);
      traceIndexBuild(`built=${indexBuildDelta} segments=${inputs.segments.length}`);
    }
    this.metrics.recordSegmentCull({ visible: segments.length, total: inputs.segments.length });
    traceSegmentCull(
      `visible=${segments.length}/${inputs.segments.length} rows=[${window.rows.overscanStartIndex}..${window.rows.overscanEndIndex})`,
    );

    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    this.metrics.recordRecalculation(end - start);

    const frame: VirtualizationFrame<TRow, TSegment> = {
      window,
      rows,
      segments,
      rowsConsidered: inputs.rows.length,
      segmentsConsidered: inputs.segments.length,
      fromCache: false,
    };
    this.cache.set(window.key, frame);
    return frame;
  }

  /** Force a full recalculation on the next ``resolveFrame`` call. */
  invalidate(): void {
    this.viewportWindow.invalidate();
    this.cache.clear();
    this.segmentWindowing.invalidate();
    this.metrics.recordInvalidation();
    traceVirtualizationInvalidate("full");
  }

  /** Reconfigure overscan — flushes the window cache. */
  setOverscan(overscan: Partial<OverscanConfig>): void {
    this.viewportWindow.setOverscan(overscan);
    this.cache.clear();
  }

  currentOverscan(): OverscanConfig {
    return this.viewportWindow.currentOverscan();
  }

  /** Inspect the cached window snapshot — useful for tests + the
   *  accessibility companion. */
  currentWindow() {
    return this.viewportWindow.peek();
  }

  cacheMetrics() {
    return this.cache.metrics();
  }

  segmentMetrics() {
    return this.segmentWindowing.metrics();
  }

  metricsSnapshot() {
    return this.metrics.snapshot();
  }
}
