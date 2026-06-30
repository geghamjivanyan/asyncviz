/**
 * Render pipeline.
 *
 * Composes the primitives + adapters into the work a single frame
 * does. The scheduler invokes :meth:`execute` with a callback per
 * pass; the pipeline:
 *
 *   1. snapshots + flushes the dirty-region tracker,
 *   2. collects the dirty layers from the layer manager,
 *   3. applies frame-budget degradation,
 *   4. runs the incremental renderer over the active passes,
 *   5. flushes overlays after the data pass,
 *   6. records observability + integrity hits,
 *   7. asks the frame-budget governor to evolve its state.
 *
 * The pipeline is replay-safe: given the same inputs (camera,
 * dataset, dirty regions) it issues the same passes in the same
 * order.
 */

import {
  isFullRegion,
  type DirtyRegion,
} from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import { RenderPriority } from "@/dashboard/timeline/rendering_optimization/models/render_priority";
import { type TimelineDirtyRegionTracker } from "@/dashboard/timeline/rendering_optimization/timeline_dirty_regions";
import { type TimelineFrameBudget } from "@/dashboard/timeline/rendering_optimization/timeline_frame_budget";
import {
  TimelineIncrementalRenderer,
  type PassDrawer,
} from "@/dashboard/timeline/rendering_optimization/timeline_incremental_renderer";
import { type TimelineLayerManager } from "@/dashboard/timeline/rendering_optimization/timeline_layer_manager";
import { type TimelineOverlayScheduler } from "@/dashboard/timeline/rendering_optimization/timeline_overlay_scheduler";
import {
  checkDirtyRegion,
  checkPasses,
  checkRedrawArea,
  type IntegrityViolation,
} from "@/dashboard/timeline/rendering_optimization/timeline_render_integrity";
import { type RenderOptimizationMetrics } from "@/dashboard/timeline/rendering_optimization/timeline_render_observability";
import { recordRenderOptimizationTrace } from "@/dashboard/timeline/rendering_optimization/timeline_render_tracing";

export interface PipelineDrawHooks {
  readonly drawPass: (passId: string, region: DirtyRegion | null) => void;
  readonly drawOverlay: (overlayId: string, region: DirtyRegion | null) => void;
}

export interface PipelineFrameInputs {
  readonly ctx: CanvasRenderingContext2D | null;
  readonly cssWidth: number;
  readonly cssHeight: number;
  readonly nowMs: number;
}

export interface PipelineFrameResult {
  readonly executed: boolean;
  readonly mode: "incremental" | "full" | "skip";
  readonly durationMs: number;
  readonly regionsRedrawn: number;
  readonly passesExecuted: number;
  readonly passesSkipped: number;
  readonly overlayRedraws: number;
  readonly failures: number;
  readonly violations: readonly IntegrityViolation[];
}

export class TimelineRenderPipeline {
  private readonly incrementalRenderer = new TimelineIncrementalRenderer();
  private previousDegradationStep = 0;

  constructor(
    private readonly dirty: TimelineDirtyRegionTracker,
    private readonly layers: TimelineLayerManager,
    private readonly overlays: TimelineOverlayScheduler,
    private readonly budget: TimelineFrameBudget,
    private readonly metrics: RenderOptimizationMetrics,
  ) {}

  execute(inputs: PipelineFrameInputs, hooks: PipelineDrawHooks): PipelineFrameResult {
    if (
      inputs.ctx === null ||
      inputs.cssWidth <= 0 ||
      inputs.cssHeight <= 0 ||
      (!this.dirty.isDirty() && !this.overlays.isDirty())
    ) {
      this.metrics.recordFrame({
        mode: "skip",
        durationMs: 0,
        overBudget: false,
        overHardBudget: false,
        areaPx2: 0,
        canvasAreaPx2: inputs.cssWidth * inputs.cssHeight,
      });
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

    const violations: IntegrityViolation[] = [];
    const regionsRaw = this.dirty.flush();
    const dirtyStats = this.dirty.stats();
    this.metrics.recordDirtyRegions(regionsRaw.length, dirtyStats.collapses);
    const regions: DirtyRegion[] = [];
    for (const region of regionsRaw) {
      const violation = checkDirtyRegion(region);
      if (violation !== null) {
        violations.push(violation);
        recordRenderOptimizationTrace("integrity-violation", violation.kind);
        continue;
      }
      regions.push(region);
    }

    const allPasses = this.layers.collectPasses();
    const passViolation = checkPasses(allPasses);
    if (passViolation !== null) {
      violations.push(passViolation);
      recordRenderOptimizationTrace("integrity-violation", passViolation.kind);
    }

    const degradedPasses = this.applyDegradation(allPasses);
    const passesSkipped = allPasses.length - degradedPasses.length;
    for (let i = 0; i < passesSkipped; i += 1) {
      this.metrics.recordPass({ executed: false, skipped: true, errored: false });
    }

    const start = inputs.nowMs;
    const drawnPasses = degradedPasses.map((pass) => ({
      id: pass.id,
      draw: ((region) => {
        try {
          hooks.drawPass(pass.id, region);
          this.metrics.recordPass({ executed: true, skipped: false, errored: false });
        } catch (err) {
          this.metrics.recordPass({ executed: false, skipped: false, errored: true });
          recordRenderOptimizationTrace(
            "integrity-violation",
            `pass=${pass.id} threw: ${String(err)}`,
          );
        }
      }) as PassDrawer,
    }));

    const result = this.incrementalRenderer.run({
      ctx: inputs.ctx,
      cssWidth: inputs.cssWidth,
      cssHeight: inputs.cssHeight,
      regions: regions.length === 0 ? [] : regions,
      passes: drawnPasses,
    });

    const overlayPasses = this.overlays.flush();
    for (const overlay of overlayPasses) {
      try {
        hooks.drawOverlay(overlay.id, overlay.region);
      } catch (err) {
        recordRenderOptimizationTrace(
          "integrity-violation",
          `overlay=${overlay.id} threw: ${String(err)}`,
        );
      }
    }
    const overlayStats = this.overlays.stats();
    this.metrics.recordOverlayFlush(overlayPasses.length, overlayStats.coalesced);

    this.layers.acknowledgeAll();

    const durationMs = Math.max(0, performanceNow() - start);
    const canvasAreaPx2 = inputs.cssWidth * inputs.cssHeight;
    const areaViolation = checkRedrawArea(result.areaPx2, canvasAreaPx2);
    if (areaViolation !== null) {
      violations.push(areaViolation);
      recordRenderOptimizationTrace("integrity-violation", areaViolation.kind);
    }

    this.budget.recordFrame(durationMs);
    const budgetSnapshot = this.budget.snapshot();
    if (budgetSnapshot.degradationStep > this.previousDegradationStep) {
      this.metrics.recordDegrade();
      recordRenderOptimizationTrace(
        "degrade",
        `step=${budgetSnapshot.degradationStep} duration=${durationMs.toFixed(2)}ms`,
      );
    } else if (budgetSnapshot.degradationStep < this.previousDegradationStep) {
      this.metrics.recordRestore();
      recordRenderOptimizationTrace("restore", `step=${budgetSnapshot.degradationStep}`);
    }
    this.previousDegradationStep = budgetSnapshot.degradationStep;

    this.metrics.recordFrame({
      mode: result.mode,
      durationMs,
      overBudget: this.budget.lastOverSoft(),
      overHardBudget: this.budget.lastOverHard(),
      areaPx2: result.areaPx2,
      canvasAreaPx2,
    });
    recordRenderOptimizationTrace(
      "frame",
      `mode=${result.mode} dur=${durationMs.toFixed(2)}ms area=${result.areaPx2.toFixed(0)}px2`,
    );

    return {
      executed: result.mode !== "skip",
      mode: result.mode,
      durationMs,
      regionsRedrawn: result.regionsRedrawn,
      passesExecuted: result.passesExecuted,
      passesSkipped,
      overlayRedraws: overlayPasses.length,
      failures: result.failures,
      violations,
    };
  }

  /** Apply the active degradation strategies to a pass list. Lower-
   *  priority passes are dropped first; overlays are dropped under
   *  ``drop-overlays``; keyframe-only mode keeps CRITICAL+HIGH only. */
  private applyDegradation(
    passes: readonly {
      readonly id: string;
      readonly priority: RenderPriority;
      readonly regions: readonly DirtyRegion[];
      readonly label: string;
      readonly degraded: boolean;
    }[],
  ) {
    const strategies = this.budget.activeStrategies();
    if (strategies.length === 0) return passes.slice();
    let working = passes.slice();
    if (strategies.includes("skip-low-priority")) {
      working = working.filter((p) => p.priority >= RenderPriority.NORMAL);
    }
    if (strategies.includes("drop-overlays")) {
      working = working.filter((p) => !p.id.startsWith("overlay:"));
    }
    if (strategies.includes("keyframe-only")) {
      working = working.filter(
        (p) => p.priority >= RenderPriority.HIGH || isFullRegionOnly(p.regions),
      );
    }
    return working;
  }
}

function isFullRegionOnly(regions: readonly DirtyRegion[]): boolean {
  if (regions.length === 0) return false;
  return regions.every(isFullRegion);
}

function performanceNow(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}
