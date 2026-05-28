/**
 * Adaptive frame-budget governor.
 *
 * Tracks the rolling cost of the last N frames + decides when to
 * degrade or restore. The escalation ladder is value-only — the
 * pipeline reads the strategy index and applies it; the governor
 * itself never touches canvas state.
 *
 * The governor is deterministic: feeding identical durations in
 * identical order produces an identical strategy stream.
 */

import type {
  RenderDegradationStrategy,
  RenderOptimizationConfig,
} from "@/dashboard/timeline/rendering_optimization/timeline_render_configuration";

export interface FrameBudgetSnapshot {
  /** Active strategy index inside the degradation ladder (0 = none). */
  readonly degradationStep: number;
  /** Currently-active strategies, in escalation order. */
  readonly activeStrategies: readonly RenderDegradationStrategy[];
  /** Total frames observed. */
  readonly framesObserved: number;
  /** Frames whose duration exceeded the soft budget. */
  readonly framesOverSoft: number;
  /** Frames whose duration exceeded the hard budget. */
  readonly framesOverHard: number;
  /** Number of degrade transitions (level increased). */
  readonly degradeTransitions: number;
  /** Number of restore transitions (level decreased). */
  readonly restoreTransitions: number;
  /** Running average frame duration (ms). */
  readonly meanFrameMs: number;
  /** Worst observed frame duration (ms). */
  readonly maxFrameMs: number;
}

export class TimelineFrameBudget {
  private framesObserved = 0;
  private framesOverSoft = 0;
  private framesOverHard = 0;
  private degradeTransitions = 0;
  private restoreTransitions = 0;
  private degradationStep = 0;
  private overBudgetStreak = 0;
  private underBudgetStreak = 0;
  private durationSumMs = 0;
  private maxFrameMs = 0;
  private lastFrameOverSoft = false;
  private lastFrameOverHard = false;

  constructor(private readonly config: RenderOptimizationConfig) {}

  /** Budget thresholds in ms — exposed for the pipeline. */
  budgets(): { readonly softMs: number; readonly hardMs: number } {
    return { softMs: this.config.frameBudgetMs, hardMs: this.config.frameBudgetHardMs };
  }

  /** ``true`` when the most recently recorded frame exceeded the soft
   *  budget. */
  lastOverSoft(): boolean {
    return this.lastFrameOverSoft;
  }

  /** ``true`` when the most recently recorded frame exceeded the hard
   *  budget. */
  lastOverHard(): boolean {
    return this.lastFrameOverHard;
  }

  recordFrame(durationMs: number): void {
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this.framesObserved += 1;
    this.durationSumMs += durationMs;
    if (durationMs > this.maxFrameMs) this.maxFrameMs = durationMs;

    const overSoft = durationMs > this.config.frameBudgetMs;
    const overHard = durationMs > this.config.frameBudgetHardMs;
    this.lastFrameOverSoft = overSoft;
    this.lastFrameOverHard = overHard;
    if (overSoft) this.framesOverSoft += 1;
    if (overHard) this.framesOverHard += 1;

    if (overSoft) {
      this.overBudgetStreak += 1;
      this.underBudgetStreak = 0;
      if (
        this.overBudgetStreak >= this.config.degradeAfterFrames &&
        this.degradationStep < this.config.degradationLadder.length
      ) {
        this.degradationStep += 1;
        this.degradeTransitions += 1;
        this.overBudgetStreak = 0;
      }
    } else {
      this.underBudgetStreak += 1;
      this.overBudgetStreak = 0;
      if (
        this.underBudgetStreak >= this.config.restoreAfterFrames &&
        this.degradationStep > 0
      ) {
        this.degradationStep -= 1;
        this.restoreTransitions += 1;
        this.underBudgetStreak = 0;
      }
    }
  }

  activeStrategies(): readonly RenderDegradationStrategy[] {
    return this.config.degradationLadder.slice(0, this.degradationStep);
  }

  hasStrategy(strategy: RenderDegradationStrategy): boolean {
    return this.activeStrategies().includes(strategy);
  }

  snapshot(): FrameBudgetSnapshot {
    return {
      degradationStep: this.degradationStep,
      activeStrategies: this.activeStrategies(),
      framesObserved: this.framesObserved,
      framesOverSoft: this.framesOverSoft,
      framesOverHard: this.framesOverHard,
      degradeTransitions: this.degradeTransitions,
      restoreTransitions: this.restoreTransitions,
      meanFrameMs:
        this.framesObserved > 0 ? this.durationSumMs / this.framesObserved : 0,
      maxFrameMs: this.maxFrameMs,
    };
  }

  reset(): void {
    this.framesObserved = 0;
    this.framesOverSoft = 0;
    this.framesOverHard = 0;
    this.degradeTransitions = 0;
    this.restoreTransitions = 0;
    this.degradationStep = 0;
    this.overBudgetStreak = 0;
    this.underBudgetStreak = 0;
    this.durationSumMs = 0;
    this.maxFrameMs = 0;
    this.lastFrameOverSoft = false;
    this.lastFrameOverHard = false;
  }
}
