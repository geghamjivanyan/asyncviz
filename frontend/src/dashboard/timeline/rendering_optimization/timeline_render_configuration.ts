/**
 * Configuration for the canonical render-optimization layer.
 *
 * Three presets cover the realistic range:
 *
 *   * ``default_config`` — tuned for the production dashboard.
 *   * ``lean_config``    — aggressive coalescing + low frame budgets,
 *     used on low-power devices.
 *   * ``relaxed_config`` — bigger caches + higher frame budget, useful
 *     in benchmarks where we want a single render pass to do as much
 *     work as possible.
 *
 * The configuration is *value-only* — there are no methods. The
 * render-optimization layer reads it at construction time and never
 * mutates it. All numbers have a single source of truth here so the
 * benchmarks + tests can override them deterministically.
 */

/** Strategy for degrading work under frame-budget pressure. */
export type RenderDegradationStrategy =
  "skip-low-priority" | "drop-overlays" | "coalesce-cursor" | "keyframe-only";

export interface RenderOptimizationConfig {
  /** Soft frame budget in ms. Frames that exceed it are flagged. */
  readonly frameBudgetMs: number;
  /** Hard frame budget in ms. Frames that exceed it record a violation. */
  readonly frameBudgetHardMs: number;
  /** Maximum dirty regions tracked before we merge into a full redraw. */
  readonly dirtyRegionCapacity: number;
  /** Geometry cache capacity (entries). */
  readonly geometryCacheCapacity: number;
  /** Projection cache capacity (entries). */
  readonly projectionCacheCapacity: number;
  /** Text measurement cache capacity (entries). */
  readonly textCacheCapacity: number;
  /** Maximum draw operations the batcher buffers before forcing a flush. */
  readonly drawBatchCapacity: number;
  /** Maximum off-screen canvases pooled. */
  readonly canvasPoolCapacity: number;
  /** Pixels of overscan beyond the visible window. */
  readonly overscanPx: number;
  /** Number of consecutive over-budget frames before degrading. */
  readonly degradeAfterFrames: number;
  /** Number of consecutive under-budget frames before restoring. */
  readonly restoreAfterFrames: number;
  /** Degradation strategies enabled, in escalation order. */
  readonly degradationLadder: readonly RenderDegradationStrategy[];
  /** Whether the optimizer is allowed to coalesce the replay cursor. */
  readonly coalesceReplayCursor: boolean;
  /** Whether tracing is enabled by default. */
  readonly traceEnabled: boolean;
}

export const DEFAULT_FRAME_BUDGET_MS = 16;
export const DEFAULT_HARD_FRAME_BUDGET_MS = 33;
export const DEFAULT_DIRTY_REGION_CAPACITY = 64;
export const DEFAULT_GEOMETRY_CACHE_CAPACITY = 8192;
export const DEFAULT_PROJECTION_CACHE_CAPACITY = 16;
export const DEFAULT_TEXT_CACHE_CAPACITY = 4096;
export const DEFAULT_DRAW_BATCH_CAPACITY = 8192;
export const DEFAULT_CANVAS_POOL_CAPACITY = 4;
export const DEFAULT_OVERSCAN_PX = 64;
export const DEFAULT_DEGRADE_AFTER_FRAMES = 3;
export const DEFAULT_RESTORE_AFTER_FRAMES = 60;

const DEFAULT_LADDER: readonly RenderDegradationStrategy[] = [
  "skip-low-priority",
  "coalesce-cursor",
  "drop-overlays",
  "keyframe-only",
];

export function default_config(): RenderOptimizationConfig {
  return {
    frameBudgetMs: DEFAULT_FRAME_BUDGET_MS,
    frameBudgetHardMs: DEFAULT_HARD_FRAME_BUDGET_MS,
    dirtyRegionCapacity: DEFAULT_DIRTY_REGION_CAPACITY,
    geometryCacheCapacity: DEFAULT_GEOMETRY_CACHE_CAPACITY,
    projectionCacheCapacity: DEFAULT_PROJECTION_CACHE_CAPACITY,
    textCacheCapacity: DEFAULT_TEXT_CACHE_CAPACITY,
    drawBatchCapacity: DEFAULT_DRAW_BATCH_CAPACITY,
    canvasPoolCapacity: DEFAULT_CANVAS_POOL_CAPACITY,
    overscanPx: DEFAULT_OVERSCAN_PX,
    degradeAfterFrames: DEFAULT_DEGRADE_AFTER_FRAMES,
    restoreAfterFrames: DEFAULT_RESTORE_AFTER_FRAMES,
    degradationLadder: DEFAULT_LADDER,
    coalesceReplayCursor: true,
    traceEnabled: false,
  };
}

export function lean_config(): RenderOptimizationConfig {
  return {
    ...default_config(),
    frameBudgetMs: 12,
    frameBudgetHardMs: 24,
    dirtyRegionCapacity: 32,
    geometryCacheCapacity: 2048,
    projectionCacheCapacity: 8,
    textCacheCapacity: 1024,
    drawBatchCapacity: 2048,
    canvasPoolCapacity: 2,
    overscanPx: 32,
    degradeAfterFrames: 2,
    restoreAfterFrames: 90,
  };
}

export function relaxed_config(): RenderOptimizationConfig {
  return {
    ...default_config(),
    frameBudgetMs: 24,
    frameBudgetHardMs: 50,
    dirtyRegionCapacity: 128,
    geometryCacheCapacity: 32_768,
    projectionCacheCapacity: 32,
    textCacheCapacity: 16_384,
    drawBatchCapacity: 32_768,
    canvasPoolCapacity: 8,
    overscanPx: 128,
    degradeAfterFrames: 5,
    restoreAfterFrames: 30,
  };
}
