/**
 * Canonical timeline render-optimization layer.
 *
 * Public surface intentionally mirrors the established
 * runtime-layer conventions: configuration presets,
 * primitive classes, adapter classes, a single scheduler facade,
 * observability + tracing + diagnostics helpers.
 */

// Configuration + types
export {
  default_config,
  lean_config,
  relaxed_config,
  type RenderDegradationStrategy,
  type RenderOptimizationConfig,
  DEFAULT_FRAME_BUDGET_MS,
  DEFAULT_HARD_FRAME_BUDGET_MS,
  DEFAULT_DIRTY_REGION_CAPACITY,
  DEFAULT_GEOMETRY_CACHE_CAPACITY,
  DEFAULT_PROJECTION_CACHE_CAPACITY,
  DEFAULT_TEXT_CACHE_CAPACITY,
  DEFAULT_DRAW_BATCH_CAPACITY,
  DEFAULT_CANVAS_POOL_CAPACITY,
  DEFAULT_OVERSCAN_PX,
  DEFAULT_DEGRADE_AFTER_FRAMES,
  DEFAULT_RESTORE_AFTER_FRAMES,
} from "./timeline_render_configuration";

// Models
export {
  FULL_REGION_SENTINEL,
  isFullRegion,
  mergeRegions,
  regionArea,
  regionsOverlap,
  RenderPriority,
  isRenderPriority,
  makeCacheKey,
  makeVersionedKey,
  quantizeCoord,
  type DirtyRegion,
  type DirtyRegionReason,
  type RenderPass,
  type RenderPassResult,
  type CacheNamespace,
} from "./models";

// Primitives
export { TimelineDirtyRegionTracker, type DirtyRegionStats } from "./timeline_dirty_regions";
export { TimelineFrameBudget, type FrameBudgetSnapshot } from "./timeline_frame_budget";
export {
  TimelineGeometryCache,
  type GeometryCacheStats,
  type GeometryEntry,
} from "./timeline_geometry_cache";
export {
  TimelineProjectionCache,
  type ProjectionCacheStats,
  type ProjectionEntry,
} from "./timeline_projection_cache";
export {
  TimelineTextRenderer,
  type TextMeasurer,
  type TextMetricsEntry,
  type TextRendererStats,
  type MeasurableTextMetrics,
  canvasTextMeasurer,
} from "./timeline_text_renderer";
export {
  TimelineDrawBatcher,
  type BatcherStats,
  type DrawOp,
  type DrawOpKind,
  type LineDrawOp,
  type RectDrawOp,
  type StrokeRectDrawOp,
} from "./timeline_draw_batcher";
export {
  TimelineCanvasPool,
  documentCanvasFactory,
  type CanvasFactory,
  type CanvasPoolStats,
  type PooledCanvas,
} from "./timeline_canvas_pool";
export { BoundedLruMap, type BoundedLruStats } from "./utils/bounded_lru";

// Adapters
export {
  TimelineLayerManager,
  type LayerDescriptor,
  type LayerManagerStats,
} from "./timeline_layer_manager";
export {
  TimelineOverlayScheduler,
  type OverlayDescriptor,
  type OverlayStats,
} from "./timeline_overlay_scheduler";
export {
  TimelineViewportCuller,
  type CullableBounds,
  type ViewportCullingStats,
} from "./timeline_viewport_culling";
export {
  TimelineReplayRenderCoordinator,
  type ReplayCoordinatorStats,
  type ReplayCursorTick,
} from "./timeline_replay_rendering";
export {
  TimelineIncrementalRenderer,
  type IncrementalRenderInputs,
  type IncrementalRenderResult,
  type PassDrawer,
} from "./timeline_incremental_renderer";

// Pipeline + scheduler facade
export {
  TimelineRenderPipeline,
  type PipelineDrawHooks,
  type PipelineFrameInputs,
  type PipelineFrameResult,
} from "./timeline_render_pipeline";
export {
  TimelineRenderScheduler,
  type FlushPassResult,
  type RenderSchedulerOptions,
} from "./timeline_render_scheduler";

// Integrity
export {
  checkDirtyRegion,
  checkPasses,
  checkRedrawArea,
  type IntegrityViolation,
  type IntegrityViolationKind,
} from "./timeline_render_integrity";

// Observability
export {
  RenderOptimizationMetrics,
  getRenderOptimizationMetrics,
  resetRenderOptimizationMetrics,
  type RenderOptimizationMetricsSnapshot,
} from "./timeline_render_observability";

// Tracing
export {
  RENDER_OPT_TRACE_CAPACITY,
  clearRenderOptimizationTrace,
  getRenderOptimizationTrace,
  isRenderOptimizationTraceEnabled,
  recordRenderOptimizationTrace,
  setRenderOptimizationTraceEnabled,
  type RenderOptimizationTraceEntry,
  type RenderOptimizationTraceKind,
} from "./timeline_render_tracing";

// Diagnostics
export {
  buildRenderOptimizationDiagnostics,
  type RenderOptimizationDiagnostics,
  type RenderOptimizationDiagnosticsInputs,
} from "./timeline_render_diagnostics";
