/**
 * Segment-specific windowing facade.
 *
 * Owns the per-dataset spatial-index lifecycle: build on first use
 * or after a sequence change; reuse otherwise. Returns the culled
 * list for the supplied window.
 */

import {
  cullSegmentsIndexed,
  cullSegmentsLinear,
} from "@/dashboard/timeline/virtualization/TimelineVisibilityCulling";
import {
  TimelineSegmentSpatialIndex,
  type SpatialIndexable,
} from "@/dashboard/timeline/virtualization/utils/spatialIndex";
import type {
  TimelineRowWindow,
  TimelineTimeWindow,
} from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";

export interface SegmentWindowingOptions {
  /** Skip the spatial index — falls back to linear culling. Useful
   *  for tests / tiny datasets. */
  disableIndex?: boolean;
  /** Threshold below which the index is skipped (small datasets are
   *  faster to linear-scan than to bucket). */
  indexMinSegments?: number;
}

const DEFAULT_INDEX_MIN_SEGMENTS = 256;

export class TimelineSegmentWindowing<TSegment extends SpatialIndexable> {
  private index: TimelineSegmentSpatialIndex<TSegment> | null = null;
  private builtForSequence: number = -1;
  private builtForLength: number = -1;
  private readonly options: Required<SegmentWindowingOptions>;
  private _builds = 0;

  constructor(options: SegmentWindowingOptions = {}) {
    this.options = {
      disableIndex: options.disableIndex ?? false,
      indexMinSegments: options.indexMinSegments ?? DEFAULT_INDEX_MIN_SEGMENTS,
    };
  }

  /** Resolve segments visible inside ``window``. Builds (or reuses)
   *  the spatial index for the current sequence. */
  resolve(args: {
    segments: readonly TSegment[];
    sequence: number;
    rowWindow: TimelineRowWindow;
    timeWindow: TimelineTimeWindow;
  }): TSegment[] {
    const { segments, sequence, rowWindow, timeWindow } = args;
    if (segments.length === 0) return [];
    if (
      this.options.disableIndex ||
      segments.length < this.options.indexMinSegments
    ) {
      this.index = null;
      this.builtForSequence = sequence;
      this.builtForLength = segments.length;
      return cullSegmentsLinear({ segments, rowWindow, timeWindow });
    }
    if (
      this.index === null ||
      this.builtForSequence !== sequence ||
      this.builtForLength !== segments.length
    ) {
      this.index = new TimelineSegmentSpatialIndex<TSegment>(segments);
      this.builtForSequence = sequence;
      this.builtForLength = segments.length;
      this._builds += 1;
    }
    return cullSegmentsIndexed({ index: this.index, rowWindow, timeWindow });
  }

  invalidate(): void {
    this.index = null;
    this.builtForSequence = -1;
    this.builtForLength = -1;
  }

  metrics(): { indexBuilds: number; indexed: boolean; indexed_sequence: number } {
    return {
      indexBuilds: this._builds,
      indexed: this.index !== null,
      indexed_sequence: this.builtForSequence,
    };
  }
}
