/**
 * Canonical invalidation tracker for the live engine.
 *
 * The tracker is a small, allocation-friendly accumulator that the
 * delta processor / replay coordinator / animation clock push regions
 * into. The engine calls :meth:`drain` once per flush to pull a
 * coalesced :type:`InvalidationBatch` ready for the renderer.
 *
 * Determinism rules:
 *
 *   * regions are absorbed in insertion order,
 *   * empty batches are stable references (``EMPTY_INVALIDATION_BATCH``),
 *   * the tracker is *not* a ring buffer — it grows during a frame
 *     window, then resets on drain.
 */

import {
  EMPTY_INVALIDATION_BATCH,
  type DirtyRegion,
  type InvalidationBatch,
  type InvalidationReason,
} from "@/dashboard/timeline/live/models/TimelineLiveModels";
import { coalesceRegions } from "@/dashboard/timeline/live/TimelineDirtyRegions";

export interface PushRegionArgs {
  reason: InvalidationReason;
  taskIds?: readonly string[];
  segmentIds?: readonly string[];
  sequence?: number | null;
  atMs?: number;
}

export class TimelineInvalidationTracker {
  private regions: DirtyRegion[] = [];
  private _pushed = 0;
  private _drained = 0;

  push(args: PushRegionArgs): void {
    this.regions.push({
      reason: args.reason,
      taskIds: args.taskIds,
      segmentIds: args.segmentIds,
      sequence: args.sequence ?? null,
      atMs: args.atMs ?? defaultNow(),
    });
    this._pushed += 1;
  }

  isDirty(): boolean {
    return this.regions.length > 0;
  }

  /** Pull every pending region into a single :type:`InvalidationBatch`
   *  and reset the accumulator. */
  drain(): InvalidationBatch {
    if (this.regions.length === 0) return EMPTY_INVALIDATION_BATCH;
    const batch = coalesceRegions(this.regions);
    this.regions = [];
    this._drained += 1;
    return batch;
  }

  /** Peek the batch without consuming — used by diagnostics. */
  peek(): InvalidationBatch {
    if (this.regions.length === 0) return EMPTY_INVALIDATION_BATCH;
    return coalesceRegions(this.regions);
  }

  /** Reset without producing a batch — used on disposal. */
  clear(): void {
    this.regions = [];
  }

  size(): number {
    return this.regions.length;
  }

  totalPushed(): number {
    return this._pushed;
  }

  totalDrained(): number {
    return this._drained;
  }
}

function defaultNow(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}
