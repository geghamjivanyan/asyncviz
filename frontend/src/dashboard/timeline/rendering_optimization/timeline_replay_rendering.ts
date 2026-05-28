/**
 * Replay-aware redraw coordinator.
 *
 * Replay rendering has two characteristics the optimization layer
 * must respect:
 *
 *   1. **Determinism.** Given the same sequence id, the same set of
 *      pixels must paint. The coordinator therefore tracks the active
 *      sequence + only invalidates the cursor region on advance.
 *
 *   2. **High-frequency cursor moves.** During playback the cursor
 *      moves 60+ times a second. Coalescing cursor updates into a
 *      single overlay redraw per frame is essential.
 *
 * This module owns the "what changed since last cursor frame" math.
 * The drawing itself happens in the overlay layer the renderer
 * already exposes; this module emits dirty regions + decides when a
 * keyframe (full redraw) is required.
 */

import {
  FULL_REGION_SENTINEL,
  type DirtyRegion,
} from "@/dashboard/timeline/rendering_optimization/models/dirty_region";

export interface ReplayCursorTick {
  /** Replay sequence the cursor is parked on. */
  readonly sequence: number;
  /** World-time the cursor maps to (seconds). */
  readonly timeSeconds: number;
  /** ``true`` when this tick should force a full redraw (e.g. seek). */
  readonly keyframe?: boolean;
}

export interface ReplayCoordinatorStats {
  readonly cursorTicksObserved: number;
  readonly cursorRegionsEmitted: number;
  readonly keyframesEmitted: number;
  readonly coalescedTicks: number;
  readonly lastSequence: number | null;
  readonly lastTimeSeconds: number | null;
}

export class TimelineReplayRenderCoordinator {
  private lastSequence: number | null = null;
  private lastTimeSeconds: number | null = null;
  private cursorTicksObserved = 0;
  private cursorRegionsEmitted = 0;
  private keyframesEmitted = 0;
  private coalescedTicks = 0;
  private pendingTick: ReplayCursorTick | null = null;

  /** Record a cursor tick. The actual dirty region is produced when
   *  the scheduler asks the coordinator to emit (typically once per
   *  frame). Successive ticks within the same frame are coalesced to
   *  the latest. */
  recordCursorTick(tick: ReplayCursorTick): void {
    this.cursorTicksObserved += 1;
    if (this.pendingTick !== null) this.coalescedTicks += 1;
    this.pendingTick = tick;
  }

  /** Drain the pending cursor tick into the equivalent dirty region.
   *  Coalescing ensures we emit at most one region per frame. */
  emit(cursorBand: { y: number; height: number }): DirtyRegion | null {
    const tick = this.pendingTick;
    if (tick === null) return null;
    this.pendingTick = null;

    if (tick.keyframe || this.lastSequence === null) {
      this.keyframesEmitted += 1;
      this.lastSequence = tick.sequence;
      this.lastTimeSeconds = tick.timeSeconds;
      return FULL_REGION_SENTINEL;
    }

    const fromX = approximateCursorX(this.lastTimeSeconds ?? 0);
    const toX = approximateCursorX(tick.timeSeconds);
    const x = Math.min(fromX, toX) - 2;
    const width = Math.abs(toX - fromX) + 4;
    this.cursorRegionsEmitted += 1;
    this.lastSequence = tick.sequence;
    this.lastTimeSeconds = tick.timeSeconds;
    return {
      x,
      y: cursorBand.y,
      width,
      height: cursorBand.height,
      reason: "replay",
    };
  }

  /** Reset cursor state — used on replay-session changes / scrubs. */
  resetCursor(): void {
    this.lastSequence = null;
    this.lastTimeSeconds = null;
    this.pendingTick = null;
  }

  hasPendingTick(): boolean {
    return this.pendingTick !== null;
  }

  stats(): ReplayCoordinatorStats {
    return {
      cursorTicksObserved: this.cursorTicksObserved,
      cursorRegionsEmitted: this.cursorRegionsEmitted,
      keyframesEmitted: this.keyframesEmitted,
      coalescedTicks: this.coalescedTicks,
      lastSequence: this.lastSequence,
      lastTimeSeconds: this.lastTimeSeconds,
    };
  }

  reset(): void {
    this.resetCursor();
    this.cursorTicksObserved = 0;
    this.cursorRegionsEmitted = 0;
    this.keyframesEmitted = 0;
    this.coalescedTicks = 0;
  }
}

/**
 * The coordinator emits time-relative regions; the renderer maps them
 * to actual pixels at flush time using the live coordinate system.
 * We use a placeholder linear projection here so the coordinator can
 * operate without a coordinate dependency in tests.
 */
function approximateCursorX(timeSeconds: number): number {
  return timeSeconds * 1000;
}
