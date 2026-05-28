/**
 * Canonical time-scaling engine.
 *
 * The engine owns the *single source of truth* for the time-axis
 * transform every other timeline subsystem consults: virtualization,
 * tick rendering, hit testing, replay scrubbing. It composes:
 *
 *   * :class:`TimelineTimeScale` — immutable transform primitive,
 *   * :func:`normalizeViewport` — constraint + precision guard,
 *   * :func:`generateTicks` — dynamic tick generation,
 *   * :class:`TimelineScaleTickCache` — bounded tick cache,
 *   * :class:`ScaleInvalidationBus` — subscriber fanout for engine
 *     consumers,
 *   * :class:`TimelineScaleMetrics` — observability.
 *
 * Determinism rules:
 *
 *   * the scale snapshot is immutable per epoch — consumers compare
 *     by ``===``,
 *   * the tick cache key is the scale key,
 *   * every mutation routes through :meth:`applyWindow` so
 *     constraints + precision guards run exactly once.
 */

import {
  safeScale,
  type TimelineTimeScale,
} from "@/dashboard/timeline/scaling/TimelineTimeScale";
import {
  normalizeViewport,
  type NormalizeViewportResult,
} from "@/dashboard/timeline/scaling/TimelineScaleNormalization";
import {
  generateTicks,
  type GenerateTicksOptions,
} from "@/dashboard/timeline/scaling/TimelineScaleTicks";
import { TimelineScaleTickCache } from "@/dashboard/timeline/scaling/TimelineScaleCache";
import {
  ScaleInvalidationBus,
  type ScaleInvalidationKind,
  type ScaleInvalidationListener,
} from "@/dashboard/timeline/scaling/TimelineScaleInvalidation";
import {
  getTimelineScaleMetrics,
  type TimelineScaleMetrics,
} from "@/dashboard/timeline/scaling/TimelineScaleMetrics";
import {
  isAtConstraintEdge,
  mergeConstraints,
} from "@/dashboard/timeline/scaling/TimelineScaleConstraints";
import {
  panScale,
  fitScaleToRange,
  zoomScaleAroundTime,
  zoomScaleAroundX,
} from "@/dashboard/timeline/scaling/TimelineScaleTransforms";
import {
  DEFAULT_SCALE_CONSTRAINTS,
  type ScaleConstraints,
  type TimelineTickList,
} from "@/dashboard/timeline/scaling/models/TimelineScaleModels";
import {
  EMPTY_SCALE_VIEWPORT,
  viewportChanged,
  type ScaleViewport,
} from "@/dashboard/timeline/scaling/TimelineScaleViewport";
import {
  traceConstraintHit,
  traceFit,
  traceNormalize,
  tracePan,
  tracePrecisionWarning,
  traceScaleInvalidate,
  traceScaleSet,
  traceTickBuild,
  traceTickCacheHit,
  traceZoom,
} from "@/dashboard/timeline/scaling/TimelineScaleTracing";

export interface TimelineScaleEngineOptions {
  initialTimeStart?: number;
  initialTimeEnd?: number;
  initialViewport?: ScaleViewport;
  constraints?: Partial<ScaleConstraints>;
  metrics?: TimelineScaleMetrics;
  tickCache?: TimelineScaleTickCache;
  tickOptions?: GenerateTicksOptions;
}

export class TimelineScaleEngine {
  private scale: TimelineTimeScale;
  private viewport: ScaleViewport;
  private constraints: ScaleConstraints;
  private readonly bus = new ScaleInvalidationBus();
  private readonly tickCache: TimelineScaleTickCache;
  private readonly metrics: TimelineScaleMetrics;
  private readonly tickOptions: GenerateTicksOptions;

  constructor(options: TimelineScaleEngineOptions = {}) {
    this.constraints = mergeConstraints(DEFAULT_SCALE_CONSTRAINTS, options.constraints ?? {});
    this.metrics = options.metrics ?? getTimelineScaleMetrics();
    this.tickCache = options.tickCache ?? new TimelineScaleTickCache();
    this.tickOptions = options.tickOptions ?? {};
    this.viewport = options.initialViewport ?? EMPTY_SCALE_VIEWPORT;
    const timeStart = options.initialTimeStart ?? 0;
    const timeEnd = options.initialTimeEnd ?? Math.max(1, timeStart + 1);
    const width = Math.max(1, this.viewport.widthPx);
    this.scale = this.normalizeAndBuild(timeStart, timeEnd, width);
  }

  // ── public API ───────────────────────────────────────────────────

  currentScale(): TimelineTimeScale {
    return this.scale;
  }

  currentConstraints(): ScaleConstraints {
    return this.constraints;
  }

  currentViewport(): ScaleViewport {
    return this.viewport;
  }

  /** Replace the active scale window directly. */
  setTimeWindow(timeStart: number, timeEnd: number): TimelineTimeScale {
    const next = this.normalizeAndBuild(timeStart, timeEnd, this.viewport.widthPx);
    this.commit(next, "scale-window");
    this.metrics.recordScaleChange("set");
    traceScaleSet(`start=${next.timeStart} end=${next.timeEnd}`);
    return this.scale;
  }

  /** Replace the viewport (width / dpr). Re-normalizes the active
   *  scale against the new width. */
  setViewport(viewport: ScaleViewport): TimelineTimeScale {
    if (!viewportChanged(this.viewport, viewport)) return this.scale;
    this.viewport = viewport;
    const next = this.normalizeAndBuild(
      this.scale.timeStart,
      this.scale.timeEnd,
      viewport.widthPx,
    );
    this.commit(next, "viewport");
    return this.scale;
  }

  /** Pan the scale by ``deltaSeconds``. */
  pan(deltaSeconds: number): TimelineTimeScale {
    const { timeStart, timeEnd } = panScale(this.scale, deltaSeconds);
    const next = this.normalizeAndBuild(timeStart, timeEnd, this.viewport.widthPx);
    this.commit(next, "scale-window");
    this.metrics.recordScaleChange("pan");
    tracePan(`delta=${deltaSeconds}`);
    return this.scale;
  }

  /** Zoom around a world-time anchor. */
  zoomAroundTime(anchorSeconds: number, factor: number): TimelineTimeScale {
    const { timeStart, timeEnd } = zoomScaleAroundTime(this.scale, anchorSeconds, factor);
    const next = this.normalizeAndBuild(timeStart, timeEnd, this.viewport.widthPx);
    this.commit(next, "scale-window");
    this.metrics.recordScaleChange("zoom");
    traceZoom(`anchor=${anchorSeconds} factor=${factor}`);
    return this.scale;
  }

  /** Zoom around a CSS pixel anchor. */
  zoomAroundX(xCss: number, factor: number): TimelineTimeScale {
    const { timeStart, timeEnd } = zoomScaleAroundX(this.scale, xCss, factor);
    const next = this.normalizeAndBuild(timeStart, timeEnd, this.viewport.widthPx);
    this.commit(next, "scale-window");
    this.metrics.recordScaleChange("zoom");
    traceZoom(`anchorX=${xCss} factor=${factor}`);
    return this.scale;
  }

  /** Fit the scale to exactly cover ``[start, end]``. */
  fitToRange(startSeconds: number, endSeconds: number): TimelineTimeScale {
    const { timeStart, timeEnd } = fitScaleToRange(this.scale, startSeconds, endSeconds);
    const next = this.normalizeAndBuild(timeStart, timeEnd, this.viewport.widthPx);
    this.commit(next, "scale-window");
    this.metrics.recordScaleChange("fit");
    traceFit(`range=${startSeconds}..${endSeconds}`);
    return this.scale;
  }

  /** Replace constraints. */
  setConstraints(constraints: Partial<ScaleConstraints>): TimelineTimeScale {
    this.constraints = mergeConstraints(this.constraints, constraints);
    const next = this.normalizeAndBuild(
      this.scale.timeStart,
      this.scale.timeEnd,
      this.viewport.widthPx,
    );
    this.commit(next, "constraints");
    return this.scale;
  }

  /** Force-invalidate listeners + clear caches without changing the
   *  scale window. */
  invalidate(): void {
    this.tickCache.clear();
    this.bus.emit("manual");
    this.metrics.recordInvalidation("manual");
    traceScaleInvalidate("manual");
  }

  /** Subscribe to scale invalidations. */
  subscribe(listener: ScaleInvalidationListener): () => void {
    return this.bus.subscribe(listener);
  }

  /** Generate ticks for the active scale. Cached. */
  ticks(options?: GenerateTicksOptions): TimelineTickList {
    const cached = this.tickCache.get(this.scale.key);
    if (cached !== null) {
      this.metrics.recordTickGeneration(0, true);
      traceTickCacheHit(`key=${this.scale.key}`);
      return cached;
    }
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const list = generateTicks(this.scale, { ...this.tickOptions, ...options });
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    this.metrics.recordTickGeneration(end - start, false);
    this.tickCache.set(this.scale.key, list);
    traceTickBuild(`key=${this.scale.key} ticks=${list.ticks.length}`);
    return list;
  }

  /** Snapshot consumers can stash for diagnostics. */
  metricsSnapshot() {
    return this.metrics.snapshot();
  }

  tickCacheMetrics() {
    return this.tickCache.metrics();
  }

  // ── internals ────────────────────────────────────────────────────

  private normalizeAndBuild(
    timeStart: number,
    timeEnd: number,
    widthPx: number,
  ): TimelineTimeScale {
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const normalized: NormalizeViewportResult = normalizeViewport({
      timeStart,
      timeEnd,
      widthPx,
      devicePixelRatio: this.viewport.devicePixelRatio,
      constraints: this.constraints,
    });
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    this.metrics.recordViewportNormalization(end - start, normalized.nearPrecisionFloor);
    traceNormalize(
      `start=${normalized.timeStart} end=${normalized.timeEnd} adjusted=${normalized.adjusted} reason=${normalized.reason}`,
    );
    if (normalized.nearPrecisionFloor) {
      tracePrecisionWarning(`duration=${normalized.timeEnd - normalized.timeStart}`);
    }
    const duration = normalized.timeEnd - normalized.timeStart;
    const edge = isAtConstraintEdge(duration, this.constraints);
    if (edge === "min") {
      this.metrics.recordConstraintHit("min");
      traceConstraintHit("min");
    } else if (edge === "max") {
      this.metrics.recordConstraintHit("max");
      traceConstraintHit("max");
    }
    return safeScale(normalized.timeStart, normalized.timeEnd, normalized.widthPx);
  }

  private commit(next: TimelineTimeScale, kind: ScaleInvalidationKind): void {
    if (next.key === this.scale.key) return;
    this.scale = next;
    this.tickCache.clear();
    this.bus.emit(kind);
    this.metrics.recordInvalidation(kind);
  }
}
