/**
 * Value types describing a single render pass.
 *
 * A render *pass* is the unit of work consumed by the
 * :class:`TimelineRenderPipeline`. It carries the layer to draw, the
 * priority bucket, the regions it touches, and a label for tracing.
 */

import type { DirtyRegion } from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import type { RenderPriority } from "@/dashboard/timeline/rendering_optimization/models/render_priority";

export interface RenderPass {
  /** Stable identifier — typically the layer id. */
  readonly id: string;
  /** Priority bucket. */
  readonly priority: RenderPriority;
  /** Regions this pass touches (used to compute redraw cost). */
  readonly regions: readonly DirtyRegion[];
  /** Human-readable label for diagnostics + tracing. */
  readonly label: string;
  /** ``true`` when the pass is currently degraded (skipped/reduced). */
  readonly degraded: boolean;
}

export interface RenderPassResult {
  /** Pass that ran. */
  readonly pass: RenderPass;
  /** Wall-clock duration in ms. */
  readonly durationMs: number;
  /** Sum of dirty-region area touched (CSS px squared). */
  readonly areaPx2: number;
  /** ``true`` when the pass was skipped due to degradation. */
  readonly skipped: boolean;
  /** ``true`` when the pass raised an error (caught + recorded). */
  readonly errored: boolean;
}
