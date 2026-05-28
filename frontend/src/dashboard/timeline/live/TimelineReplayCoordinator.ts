/**
 * Replay/live transition coordinator.
 *
 * Owns the engine's "are we live or replaying right now?" state and
 * collapses replay-batch invalidations into a single flush. The
 * coordinator is intentionally tiny — most replay correctness lives
 * in the runtime store's :func:`decideStoreSequence`. Here we just
 * keep the renderer honest about *when* to redraw.
 *
 * Lifecycle:
 *
 *   1. ``beginReplay()`` — engine enters ``replay`` mode; subsequent
 *      delta processing buffers invalidations instead of flushing.
 *   2. ``applyReplayBatch(envelopes)`` — the coordinator drains the
 *      replay buffer + emits a single ``replay`` invalidation when
 *      finished.
 *   3. ``endReplay()`` — engine switches back to ``live`` mode;
 *      future deltas flush normally.
 *
 * The coordinator does NOT mutate the store — that's the runtime
 * store's responsibility. It only orchestrates render invalidation.
 */

import type { RuntimeEnvelope } from "@/types/runtime";
import type { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";
import type { TimelineDeltaProcessor } from "@/dashboard/timeline/live/TimelineDeltaProcessor";
import type { TimelineLiveMode, TimelineReplayPhase } from "@/dashboard/timeline/live/models/TimelineLiveModels";

export interface ReplayCoordinatorOptions {
  processor: TimelineDeltaProcessor;
  tracker: TimelineInvalidationTracker;
}

export interface ReplayBatchResult {
  applied: number;
  suppressed: number;
  regionsPushed: number;
}

export class TimelineReplayCoordinator {
  private mode: TimelineLiveMode = "idle";
  private phase: TimelineReplayPhase = "idle";
  private readonly processor: TimelineDeltaProcessor;
  private readonly tracker: TimelineInvalidationTracker;
  private _replayBatchesApplied = 0;
  private _envelopesApplied = 0;

  constructor(options: ReplayCoordinatorOptions) {
    this.processor = options.processor;
    this.tracker = options.tracker;
  }

  currentMode(): TimelineLiveMode {
    return this.mode;
  }

  currentPhase(): TimelineReplayPhase {
    return this.phase;
  }

  goLive(): void {
    this.mode = "live";
    this.phase = "idle";
  }

  pause(): void {
    this.mode = "paused";
  }

  idle(): void {
    this.mode = "idle";
    this.phase = "idle";
  }

  beginReplay(): void {
    this.mode = "replay";
    this.phase = "buffering";
  }

  /** Apply an ordered batch of replay envelopes. Returns aggregate
   *  stats. The tracker receives one merged ``replay`` invalidation
   *  on top of the per-envelope deltas so consumers can distinguish
   *  replay flushes from live flushes. */
  applyReplayBatch(envelopes: readonly RuntimeEnvelope[]): ReplayBatchResult {
    if (this.mode !== "replay") {
      this.mode = "replay";
      this.phase = "applying";
    } else {
      this.phase = "applying";
    }
    let applied = 0;
    let suppressed = 0;
    let regionsPushed = 0;
    let highestSequence = 0;
    for (const envelope of envelopes) {
      const result = this.processor.process(envelope, this.tracker);
      if (result.suppressed) {
        suppressed += 1;
        continue;
      }
      if (result.invalidated) regionsPushed += result.regionsPushed;
      applied += 1;
      if (envelope.sequence !== undefined && envelope.sequence !== null && envelope.sequence > highestSequence) {
        highestSequence = envelope.sequence;
      }
    }
    this.tracker.push({
      reason: "replay",
      sequence: highestSequence,
    });
    this._replayBatchesApplied += 1;
    this._envelopesApplied += applied;
    this.phase = "transitioning";
    return { applied, suppressed, regionsPushed };
  }

  endReplay(): void {
    this.mode = "live";
    this.phase = "done";
  }

  metrics(): {
    mode: TimelineLiveMode;
    phase: TimelineReplayPhase;
    replayBatchesApplied: number;
    envelopesApplied: number;
  } {
    return {
      mode: this.mode,
      phase: this.phase,
      replayBatchesApplied: this._replayBatchesApplied,
      envelopesApplied: this._envelopesApplied,
    };
  }

  reset(): void {
    this.mode = "idle";
    this.phase = "idle";
    this._replayBatchesApplied = 0;
    this._envelopesApplied = 0;
  }
}
