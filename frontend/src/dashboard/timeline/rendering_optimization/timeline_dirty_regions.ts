/**
 * Bounded dirty-region tracker.
 *
 * Drivers (camera, selection, overlay, replay) push regions; the
 * tracker keeps them merged + bounded. When the number of distinct
 * regions exceeds the configured capacity, the tracker collapses to a
 * single full-canvas region — at that point per-region redraws are no
 * longer cheaper than a full redraw.
 *
 * The tracker is *pure-value*; it owns no canvas reference.
 */

import {
  FULL_REGION_SENTINEL,
  isFullRegion,
  mergeRegions,
  regionArea,
  regionsOverlap,
  type DirtyRegion,
  type DirtyRegionReason,
} from "@/dashboard/timeline/rendering_optimization/models/dirty_region";

export interface DirtyRegionStats {
  /** Distinct regions currently tracked. */
  readonly regionCount: number;
  /** Total area in CSS px squared. */
  readonly areaPx2: number;
  /** ``true`` when the tracker has collapsed to a full-canvas redraw. */
  readonly full: boolean;
  /** Number of times we collapsed to a full redraw since the last flush. */
  readonly collapses: number;
  /** Per-reason invalidation counts since the last flush. */
  readonly byReason: Readonly<Record<DirtyRegionReason, number>>;
}

const EMPTY_REASONS: Record<DirtyRegionReason, number> = {
  data: 0,
  camera: 0,
  viewport: 0,
  selection: 0,
  overlay: 0,
  cursor: 0,
  replay: 0,
  manual: 0,
};

export class TimelineDirtyRegionTracker {
  private regions: DirtyRegion[] = [];
  private full = false;
  private collapses = 0;
  private byReason: Record<DirtyRegionReason, number> = { ...EMPTY_REASONS };

  constructor(private readonly capacity: number) {
    if (capacity <= 0) {
      throw new RangeError(`dirty-region capacity must be > 0 (got ${capacity})`);
    }
  }

  invalidate(region: DirtyRegion): void {
    this.byReason[region.reason] = (this.byReason[region.reason] ?? 0) + 1;
    if (this.full) return;
    if (isFullRegion(region)) {
      this.collapseToFull();
      return;
    }
    if (region.width <= 0 || region.height <= 0) return;
    // Merge into the first overlapping region — keeps the set small
    // and reduces cost-of-redraw.
    for (let i = 0; i < this.regions.length; i += 1) {
      if (regionsOverlap(this.regions[i]!, region)) {
        this.regions[i] = mergeRegions(this.regions[i]!, region);
        return;
      }
    }
    this.regions.push(region);
    if (this.regions.length > this.capacity) {
      this.collapseToFull();
    }
  }

  invalidateFull(reason: DirtyRegionReason = "manual"): void {
    this.byReason[reason] = (this.byReason[reason] ?? 0) + 1;
    this.collapseToFull();
  }

  /** Snapshot the current dirty set. The list is *frozen* — callers
   *  must not mutate it. */
  snapshot(): readonly DirtyRegion[] {
    if (this.full) return [FULL_REGION_SENTINEL];
    return this.regions.slice();
  }

  stats(): DirtyRegionStats {
    if (this.full) {
      return {
        regionCount: 1,
        areaPx2: Number.POSITIVE_INFINITY,
        full: true,
        collapses: this.collapses,
        byReason: { ...this.byReason },
      };
    }
    let area = 0;
    for (const region of this.regions) area += regionArea(region);
    return {
      regionCount: this.regions.length,
      areaPx2: area,
      full: false,
      collapses: this.collapses,
      byReason: { ...this.byReason },
    };
  }

  /** Clear the dirty set + reset stats. Called at the start of every
   *  render pass — the regions get consumed by the pipeline. */
  flush(): readonly DirtyRegion[] {
    const out = this.snapshot();
    this.regions = [];
    this.full = false;
    this.collapses = 0;
    this.byReason = { ...EMPTY_REASONS };
    return out;
  }

  reset(): void {
    this.regions = [];
    this.full = false;
    this.collapses = 0;
    this.byReason = { ...EMPTY_REASONS };
  }

  isDirty(): boolean {
    return this.full || this.regions.length > 0;
  }

  private collapseToFull(): void {
    if (!this.full) this.collapses += 1;
    this.regions = [];
    this.full = true;
  }
}
