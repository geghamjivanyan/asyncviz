/**
 * One-call diagnostics builder.
 *
 * Mirrors the runtime layers: a frozen snapshot that captures every
 * sub-system at a single instant. Used by the diagnostics panel +
 * benchmark scripts.
 */

import type { DirtyRegionStats } from "@/dashboard/timeline/rendering_optimization/timeline_dirty_regions";
import type { FrameBudgetSnapshot } from "@/dashboard/timeline/rendering_optimization/timeline_frame_budget";
import type { GeometryCacheStats } from "@/dashboard/timeline/rendering_optimization/timeline_geometry_cache";
import type { ProjectionCacheStats } from "@/dashboard/timeline/rendering_optimization/timeline_projection_cache";
import type { TextRendererStats } from "@/dashboard/timeline/rendering_optimization/timeline_text_renderer";
import type { BatcherStats } from "@/dashboard/timeline/rendering_optimization/timeline_draw_batcher";
import type { CanvasPoolStats } from "@/dashboard/timeline/rendering_optimization/timeline_canvas_pool";
import type { LayerManagerStats } from "@/dashboard/timeline/rendering_optimization/timeline_layer_manager";
import type { OverlayStats } from "@/dashboard/timeline/rendering_optimization/timeline_overlay_scheduler";
import type { ReplayCoordinatorStats } from "@/dashboard/timeline/rendering_optimization/timeline_replay_rendering";
import type { ViewportCullingStats } from "@/dashboard/timeline/rendering_optimization/timeline_viewport_culling";
import type { RenderOptimizationMetricsSnapshot } from "@/dashboard/timeline/rendering_optimization/timeline_render_observability";
import type { RenderOptimizationTraceEntry } from "@/dashboard/timeline/rendering_optimization/timeline_render_tracing";
import { getRenderOptimizationTrace } from "@/dashboard/timeline/rendering_optimization/timeline_render_tracing";

export interface RenderOptimizationDiagnostics {
  readonly metrics: RenderOptimizationMetricsSnapshot;
  readonly dirty: DirtyRegionStats;
  readonly budget: FrameBudgetSnapshot;
  readonly geometryCache: GeometryCacheStats;
  readonly projectionCache: ProjectionCacheStats;
  readonly textCache: TextRendererStats;
  readonly batcher: BatcherStats;
  readonly canvasPool: CanvasPoolStats;
  readonly layers: LayerManagerStats;
  readonly overlays: OverlayStats;
  readonly viewportCulling: ViewportCullingStats;
  readonly replay: ReplayCoordinatorStats;
  readonly trace: readonly RenderOptimizationTraceEntry[];
}

export interface RenderOptimizationDiagnosticsInputs {
  readonly metrics: RenderOptimizationMetricsSnapshot;
  readonly dirty: DirtyRegionStats;
  readonly budget: FrameBudgetSnapshot;
  readonly geometryCache: GeometryCacheStats;
  readonly projectionCache: ProjectionCacheStats;
  readonly textCache: TextRendererStats;
  readonly batcher: BatcherStats;
  readonly canvasPool: CanvasPoolStats;
  readonly layers: LayerManagerStats;
  readonly overlays: OverlayStats;
  readonly viewportCulling: ViewportCullingStats;
  readonly replay: ReplayCoordinatorStats;
  readonly traceLimit?: number;
}

export function buildRenderOptimizationDiagnostics(
  inputs: RenderOptimizationDiagnosticsInputs,
): RenderOptimizationDiagnostics {
  const traceLimit = inputs.traceLimit ?? 64;
  const fullTrace = getRenderOptimizationTrace();
  const trace =
    traceLimit > 0 && fullTrace.length > traceLimit
      ? fullTrace.slice(fullTrace.length - traceLimit)
      : fullTrace;
  return {
    metrics: inputs.metrics,
    dirty: inputs.dirty,
    budget: inputs.budget,
    geometryCache: inputs.geometryCache,
    projectionCache: inputs.projectionCache,
    textCache: inputs.textCache,
    batcher: inputs.batcher,
    canvasPool: inputs.canvasPool,
    layers: inputs.layers,
    overlays: inputs.overlays,
    viewportCulling: inputs.viewportCulling,
    replay: inputs.replay,
    trace,
  };
}
