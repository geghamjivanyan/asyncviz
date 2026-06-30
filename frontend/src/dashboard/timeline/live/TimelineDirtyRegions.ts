/**
 * Pure helpers for working with :type:`DirtyRegion` sets.
 *
 * The engine accumulates regions across a frame window and then
 * coalesces them into a single :type:`InvalidationBatch` before
 * handing control to the canvas renderer. Keeping the math pure
 * means the batcher can run inside a worker later.
 */

import type {
  DirtyRegion,
  InvalidationBatch,
  InvalidationReason,
} from "@/dashboard/timeline/live/models/TimelineLiveModels";
import { EMPTY_INVALIDATION_BATCH } from "@/dashboard/timeline/live/models/TimelineLiveModels";

/** Pure: fold an iterable of :type:`DirtyRegion` into one batch. */
export function coalesceRegions(regions: Iterable<DirtyRegion>): InvalidationBatch {
  const reasons = new Set<InvalidationReason>();
  const taskIds = new Set<string>();
  const segmentIds = new Set<string>();
  let highestSequence = 0;
  let regionCount = 0;
  let includesViewport = false;
  let includesActiveTick = false;

  for (const region of regions) {
    regionCount += 1;
    reasons.add(region.reason);
    if (region.reason === "viewport") includesViewport = true;
    if (region.reason === "active-tick") includesActiveTick = true;
    if (region.taskIds) for (const id of region.taskIds) taskIds.add(id);
    if (region.segmentIds) for (const id of region.segmentIds) segmentIds.add(id);
    if (
      region.sequence !== undefined &&
      region.sequence !== null &&
      region.sequence > highestSequence
    ) {
      highestSequence = region.sequence;
    }
  }

  if (regionCount === 0) return EMPTY_INVALIDATION_BATCH;

  return {
    reasons: Array.from(reasons),
    taskIds: Array.from(taskIds),
    segmentIds: Array.from(segmentIds),
    highestSequence,
    regionCount,
    includesViewport,
    includesActiveTick,
  };
}

/** Pure: ``true`` when the batch carries any actionable change. */
export function batchIsActionable(batch: InvalidationBatch): boolean {
  return batch.regionCount > 0;
}

/** Pure: ``true`` when the batch is a no-op (active tick only, no
 *  data change). The caller can use this to skip rAF requests when
 *  nothing animation-worthy is in flight. */
export function batchIsActiveTickOnly(batch: InvalidationBatch): boolean {
  if (!batch.includesActiveTick) return false;
  return (
    batch.reasons.length === 1 &&
    batch.reasons[0] === "active-tick" &&
    batch.taskIds.length === 0 &&
    batch.segmentIds.length === 0 &&
    !batch.includesViewport
  );
}

/** Pure: project a batch onto a renderer-level :type:`DirtyReason`. */
export function batchToRendererReason(
  batch: InvalidationBatch,
): "viewport" | "data" | "selection" | "overlay" | "camera" | "manual" {
  if (batch.includesViewport) return "viewport";
  if (batch.reasons.includes("selection")) return "selection";
  if (batch.includesActiveTick) return "camera";
  if (
    batch.reasons.includes("segment") ||
    batch.reasons.includes("row") ||
    batch.reasons.includes("delta-batch") ||
    batch.reasons.includes("hydration") ||
    batch.reasons.includes("replay") ||
    batch.reasons.includes("warning")
  ) {
    return "data";
  }
  return "manual";
}
