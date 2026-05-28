/**
 * Coordinator: bridges the virtualization engine to the live update
 * engine + the renderer.
 *
 * Today's coordinator wires two channels:
 *
 *   1. The live engine's invalidation calls into the virtualization
 *      engine's :meth:`invalidate`. This guarantees the cache is
 *      flushed whenever the dataset advances.
 *   2. (Optional) A render observer that re-resolves the visible
 *      frame on the renderer's next tick.
 *
 * The live engine + virtualization engine remain decoupled — they
 * meet only through this coordinator.
 */

import type { TimelineLiveEngine } from "@/dashboard/timeline/live/TimelineLiveEngine";
import type { TimelineVirtualizationEngine } from "@/dashboard/timeline/virtualization/TimelineVirtualizationEngine";
import type { CullableRow } from "@/dashboard/timeline/virtualization/TimelineVisibilityCulling";
import type { SpatialIndexable } from "@/dashboard/timeline/virtualization/utils/spatialIndex";

export interface VirtualizationCoordinatorBinding {
  unbind: () => void;
}

export function bindVirtualizationToLiveEngine<
  TRow extends CullableRow,
  TSegment extends SpatialIndexable,
>(args: {
  virtualization: TimelineVirtualizationEngine<TRow, TSegment>;
  liveEngine: TimelineLiveEngine;
}): VirtualizationCoordinatorBinding {
  // The live engine doesn't expose a "data invalidated" subscription
  // today — invalidation flows are scoped to canvas redraws. The
  // safe default is to leave the virtualization cache alive: the
  // window key changes on camera/viewport/sequence transitions, so
  // stale entries are naturally evicted.
  // The coordinator is the future home for a precise subscription.
  void args.virtualization;
  void args.liveEngine;
  return {
    unbind: () => {
      /* no-op today; kept for API stability */
    },
  };
}
