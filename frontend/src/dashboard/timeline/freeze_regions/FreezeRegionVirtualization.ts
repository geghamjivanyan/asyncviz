/**
 * Visible-window capping for freeze regions.
 *
 * Real-world runtimes rarely have more than a handful of concurrent
 * freezes — the dashboard caps to a configurable maximum visible
 * region count + reports the hidden tail so the inspector can show a
 * "+ N more freezes hidden" hint.
 *
 * Distinct from the inline culling in
 * :func:`cullVisibleFreezeRegions`: that's a geometric cull (must be
 * onscreen); this is a render-budget cap (render at most N onscreen).
 */

import type {
  FreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

export const DEFAULT_VISIBLE_FREEZE_CAP = 128;

export interface VirtualizationResult {
  visible: readonly FreezeRegionView[];
  hidden: number;
}

/** Return at most ``cap`` regions, reporting the hidden count. */
export function clampFreezeRegions(
  regions: readonly FreezeRegionView[],
  cap: number = DEFAULT_VISIBLE_FREEZE_CAP,
): VirtualizationResult {
  if (!Number.isFinite(cap) || cap <= 0 || regions.length <= cap) {
    return { visible: regions, hidden: 0 };
  }
  return {
    visible: regions.slice(0, cap),
    hidden: regions.length - cap,
  };
}
