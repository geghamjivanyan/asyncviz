/**
 * Canonical render scheduler.
 *
 * The :class:`TimelineRenderScheduler` is the top-level façade that
 * the rest of the application talks to. It owns:
 *
 *   * one :class:`TimelineDirtyRegionTracker` (what needs to redraw),
 *   * one :class:`TimelineLayerManager`        (what passes exist),
 *   * one :class:`TimelineOverlayScheduler`    (cursor / selection),
 *   * one :class:`TimelineFrameBudget`         (degradation FSM),
 *   * one :class:`TimelineGeometryCache`,
 *   * one :class:`TimelineProjectionCache`,
 *   * one :class:`TimelineTextRenderer`,
 *   * one :class:`TimelineDrawBatcher`,
 *   * one :class:`TimelineCanvasPool`,
 *   * one :class:`TimelineViewportCuller`,
 *   * one :class:`TimelineReplayRenderCoordinator`,
 *   * one :class:`TimelineRenderPipeline`.
 *
 * Public surface mirrors the existing :class:`TimelineRenderer` /
 * :class:`TimelineScheduler` so it composes with them without
 * needing a separate top-level API. The scheduler does NOT own a
 * canvas — it's pure orchestration. The pipeline accepts the canvas
 * context at flush time.
 */

import type { CanvasFactory } from "@/dashboard/timeline/rendering_optimization/timeline_canvas_pool";
import { TimelineCanvasPool } from "@/dashboard/timeline/rendering_optimization/timeline_canvas_pool";
import {
  type DirtyRegion,
  type DirtyRegionReason,
} from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import { FULL_REGION_SENTINEL } from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import {
  TimelineDirtyRegionTracker,
} from "@/dashboard/timeline/rendering_optimization/timeline_dirty_regions";
import { TimelineDrawBatcher } from "@/dashboard/timeline/rendering_optimization/timeline_draw_batcher";
import { TimelineFrameBudget } from "@/dashboard/timeline/rendering_optimization/timeline_frame_budget";
import { TimelineGeometryCache } from "@/dashboard/timeline/rendering_optimization/timeline_geometry_cache";
import {
  TimelineLayerManager,
  type LayerDescriptor,
} from "@/dashboard/timeline/rendering_optimization/timeline_layer_manager";
import {
  TimelineOverlayScheduler,
  type OverlayDescriptor,
} from "@/dashboard/timeline/rendering_optimization/timeline_overlay_scheduler";
import { TimelineProjectionCache } from "@/dashboard/timeline/rendering_optimization/timeline_projection_cache";
import {
  TimelineRenderPipeline,
  type PipelineDrawHooks,
  type PipelineFrameResult,
} from "@/dashboard/timeline/rendering_optimization/timeline_render_pipeline";
import {
  buildRenderOptimizationDiagnostics,
  type RenderOptimizationDiagnostics,
} from "@/dashboard/timeline/rendering_optimization/timeline_render_diagnostics";
import {
  type RenderOptimizationMetrics,
  getRenderOptimizationMetrics,
} from "@/dashboard/timeline/rendering_optimization/timeline_render_observability";
import {
  default_config,
  type RenderOptimizationConfig,
} from "@/dashboard/timeline/rendering_optimization/timeline_render_configuration";
import {
  recordRenderOptimizationTrace,
  setRenderOptimizationTraceEnabled,
} from "@/dashboard/timeline/rendering_optimization/timeline_render_tracing";
import {
  TimelineReplayRenderCoordinator,
  type ReplayCursorTick,
} from "@/dashboard/timeline/rendering_optimization/timeline_replay_rendering";
import { TimelineTextRenderer } from "@/dashboard/timeline/rendering_optimization/timeline_text_renderer";
import { TimelineViewportCuller } from "@/dashboard/timeline/rendering_optimization/timeline_viewport_culling";

export interface RenderSchedulerOptions {
  readonly config?: RenderOptimizationConfig;
  readonly metrics?: RenderOptimizationMetrics;
  readonly canvasFactory?: CanvasFactory;
}

export interface FlushPassResult {
  readonly result: PipelineFrameResult;
  readonly diagnostics?: RenderOptimizationDiagnostics;
}

export class TimelineRenderScheduler {
  private readonly config: RenderOptimizationConfig;
  private readonly metrics: RenderOptimizationMetrics;
  private readonly dirty: TimelineDirtyRegionTracker;
  private readonly layers: TimelineLayerManager;
  private readonly overlays: TimelineOverlayScheduler;
  private readonly budget: TimelineFrameBudget;
  private readonly geometryCache: TimelineGeometryCache;
  private readonly projectionCache: TimelineProjectionCache;
  private readonly textCache: TimelineTextRenderer;
  private readonly drawBatcher: TimelineDrawBatcher;
  private readonly canvasPool: TimelineCanvasPool;
  private readonly culler: TimelineViewportCuller;
  private readonly replay: TimelineReplayRenderCoordinator;
  private readonly pipeline: TimelineRenderPipeline;
  private disposed = false;

  constructor(options: RenderSchedulerOptions = {}) {
    this.config = options.config ?? default_config();
    this.metrics = options.metrics ?? getRenderOptimizationMetrics();
    this.dirty = new TimelineDirtyRegionTracker(this.config.dirtyRegionCapacity);
    this.layers = new TimelineLayerManager();
    this.overlays = new TimelineOverlayScheduler();
    this.budget = new TimelineFrameBudget(this.config);
    this.geometryCache = new TimelineGeometryCache(this.config.geometryCacheCapacity);
    this.projectionCache = new TimelineProjectionCache(this.config.projectionCacheCapacity);
    this.textCache = new TimelineTextRenderer(this.config.textCacheCapacity);
    this.drawBatcher = new TimelineDrawBatcher(this.config.drawBatchCapacity);
    this.canvasPool = new TimelineCanvasPool(
      this.config.canvasPoolCapacity,
      options.canvasFactory,
    );
    this.culler = new TimelineViewportCuller(this.config.overscanPx);
    this.replay = new TimelineReplayRenderCoordinator();
    this.pipeline = new TimelineRenderPipeline(
      this.dirty,
      this.layers,
      this.overlays,
      this.budget,
      this.metrics,
    );
    if (this.config.traceEnabled) {
      setRenderOptimizationTraceEnabled(true);
    }
    recordRenderOptimizationTrace(
      "diagnostic",
      `scheduler-started config.frameBudgetMs=${this.config.frameBudgetMs}`,
    );
  }

  // ── Layer + overlay registration ──────────────────────────────────

  registerLayer(descriptor: LayerDescriptor): void {
    this.layers.register(descriptor);
  }

  registerOverlay(descriptor: OverlayDescriptor): void {
    this.overlays.register(descriptor);
  }

  // ── Dirty-region API ──────────────────────────────────────────────

  invalidateRegion(region: DirtyRegion): void {
    if (this.disposed) return;
    this.metrics.recordInvalidation(region.reason);
    this.dirty.invalidate(region);
    this.layers.invalidate(region);
  }

  invalidateFull(reason: DirtyRegionReason = "manual"): void {
    if (this.disposed) return;
    this.metrics.recordInvalidation(reason);
    this.dirty.invalidateFull(reason);
    this.layers.invalidateAll({ ...FULL_REGION_SENTINEL, reason });
  }

  requestOverlayRedraw(overlayId: string, region: DirtyRegion | null): void {
    if (this.disposed) return;
    this.overlays.requestOverlayRedraw(overlayId, region);
  }

  recordCursorTick(tick: ReplayCursorTick): void {
    if (this.disposed) return;
    this.replay.recordCursorTick(tick);
  }

  emitCursorRegion(cursorBand: { y: number; height: number }): void {
    const region = this.replay.emit(cursorBand);
    if (region === null) return;
    if (region.reason === "replay" && Number.isFinite(region.width)) {
      this.metrics.recordCursorIncrementalRedraw();
    } else {
      this.metrics.recordCursorKeyframe();
    }
    this.invalidateRegion(region);
  }

  // ── Flush ──────────────────────────────────────────────────────────

  flushRenderPass(
    ctx: CanvasRenderingContext2D | null,
    cssWidth: number,
    cssHeight: number,
    hooks: PipelineDrawHooks,
  ): PipelineFrameResult {
    if (this.disposed) {
      return {
        executed: false,
        mode: "skip",
        durationMs: 0,
        regionsRedrawn: 0,
        passesExecuted: 0,
        passesSkipped: 0,
        overlayRedraws: 0,
        failures: 0,
        violations: [],
      };
    }
    const nowMs = typeof performance !== "undefined" ? performance.now() : Date.now();
    return this.pipeline.execute(
      { ctx, cssWidth, cssHeight, nowMs },
      hooks,
    );
  }

  // ── Cache / culling accessors ─────────────────────────────────────

  geometry(): TimelineGeometryCache {
    return this.geometryCache;
  }

  projections(): TimelineProjectionCache {
    return this.projectionCache;
  }

  text(): TimelineTextRenderer {
    return this.textCache;
  }

  batcher(): TimelineDrawBatcher {
    return this.drawBatcher;
  }

  pool(): TimelineCanvasPool {
    return this.canvasPool;
  }

  culling(): TimelineViewportCuller {
    return this.culler;
  }

  replayCoordinator(): TimelineReplayRenderCoordinator {
    return this.replay;
  }

  // ── Diagnostics ───────────────────────────────────────────────────

  diagnostics(traceLimit?: number): RenderOptimizationDiagnostics {
    return buildRenderOptimizationDiagnostics({
      metrics: this.metrics.snapshot(),
      dirty: this.dirty.stats(),
      budget: this.budget.snapshot(),
      geometryCache: this.geometryCache.stats(),
      projectionCache: this.projectionCache.stats(),
      textCache: this.textCache.stats(),
      batcher: this.drawBatcher.stats(),
      canvasPool: this.canvasPool.stats(),
      layers: this.layers.stats(),
      overlays: this.overlays.stats(),
      viewportCulling: this.culler.stats(),
      replay: this.replay.stats(),
      traceLimit,
    });
  }

  // ── Lifecycle ─────────────────────────────────────────────────────

  reset(): void {
    this.dirty.reset();
    this.layers.clear();
    this.overlays.clear();
    this.budget.reset();
    this.geometryCache.clear();
    this.projectionCache.clear();
    this.textCache.clear();
    this.drawBatcher.reset();
    this.drawBatcher.resetStats();
    this.canvasPool.clear();
    this.culler.reset();
    this.replay.reset();
    recordRenderOptimizationTrace("diagnostic", "scheduler-reset");
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.reset();
    recordRenderOptimizationTrace("diagnostic", "scheduler-disposed");
  }

  get configuration(): RenderOptimizationConfig {
    return this.config;
  }
}
