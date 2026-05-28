/**
 * Segment projection model shared by the segments package.
 *
 * The projection is a *deterministic*, render-ready view of every
 * lifecycle segment in the active timeline window. It is built on
 * top of the canonical :type:`TimelineRenderSegment` so existing
 * layers keep consuming the same scene shape.
 *
 * Determinism rules:
 *
 *   * stable identity via ``segmentId``,
 *   * deterministic ordering: ``(rowIndex, startSeconds, segmentId)``,
 *   * every projection captures a ``sequence`` cursor — replay folds
 *     deltas without divergence,
 *   * timestamps are monotonic seconds so cameras stay frame-stable.
 */

import type {
  TimelineRenderSegment,
  TimelineRowWarningSeverity,
  TimelineSegmentLifecycleState,
  TimelineSegmentReplayMark,
} from "@/dashboard/timeline/rendering/TimelineLayer";

/** Single segment in the projection — superset of the scene segment. */
export interface TimelineSegmentProjectionEntry extends TimelineRenderSegment {
  /** Stable id — identical to ``segmentId``; gives consumers a future
   *  hook to diverge once flamegraph-style stacked segments land. */
  entryId: string;
  /** Resolved lifecycle state (never ``undefined`` here). */
  lifecycleState: TimelineSegmentLifecycleState;
  /** Cached duration in seconds (positive, may be 0 for sub-ns spans). */
  durationSeconds: number;
  /** Resolved warning severity (may be ``null``). */
  warningSeverity: TimelineRowWarningSeverity | null;
  /** Resolved replay mark, or ``null``. */
  replay: TimelineSegmentReplayMark | null;
  /** Resolved parent task id, or ``null``. */
  parentTaskId: string | null;
  /** Resolved lineage depth (defaults to 0). */
  depth: number;
}

export interface TimelineSegmentProjection {
  /** Segments in deterministic order. */
  segments: readonly TimelineSegmentProjectionEntry[];
  /** Lookup from ``segmentId`` → index into ``segments``. */
  indexBySegmentId: ReadonlyMap<string, number>;
  /** Lookup from ``taskId`` → list of indices for that task. */
  indicesByTaskId: ReadonlyMap<string, readonly number[]>;
  /** Sequence cursor when the projection was built. */
  sequence: number;
  /** Total segment count — convenience field. */
  totalSegments: number;
  /** ``true`` when at least one entry is still open (``isActive``). */
  hasActiveSegments: boolean;
}

export const EMPTY_TIMELINE_SEGMENT_PROJECTION: TimelineSegmentProjection = Object.freeze({
  segments: Object.freeze([]) as readonly TimelineSegmentProjectionEntry[],
  indexBySegmentId: new Map(),
  indicesByTaskId: new Map(),
  sequence: 0,
  totalSegments: 0,
  hasActiveSegments: false,
});
