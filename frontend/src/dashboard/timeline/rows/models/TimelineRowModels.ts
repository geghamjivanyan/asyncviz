/**
 * Row projection model shared by the rows package.
 *
 * The row projection is a *thin, deterministic* view of the runtime
 * store from the perspective of timeline-row rendering. It mirrors the
 * structure passed into the renderer and keeps a small bag of
 * metadata layers can rely on without re-reading the store.
 *
 * Determinism rules:
 *
 *   * row ordering is stable across renders for the same input,
 *   * row identity is the ``rowId`` field (== ``taskId`` today; will
 *     diverge for grouped lanes later),
 *   * every projection captures a ``sequence`` cursor — replay folds
 *     deltas without divergence,
 *   * timestamps are monotonic seconds so cameras stay frame-stable.
 */

import type {
  TimelineRow,
  TimelineRowReplayMark,
  TimelineRowState,
  TimelineRowWarningSeverity,
} from "@/dashboard/timeline/rendering/TimelineLayer";

/** Single row in the row projection. Superset of the canvas
 *  :type:`TimelineRow` so existing layers can render it as-is. */
export interface TimelineRowProjectionEntry extends TimelineRow {
  /** Stable id — identical to ``taskId`` today, distinct once grouping lands. */
  rowId: string;
  /** Resolved lifecycle bucket (never ``undefined`` here). */
  state: TimelineRowState;
  /** Lineage parent id, or ``null`` for roots. */
  parentTaskId: string | null;
  /** Lineage depth, always defined. */
  depth: number;
  /** Direct child count, always defined. */
  childCount: number;
  /** Highest active warning severity, or ``null``. */
  warningSeverity: TimelineRowWarningSeverity | null;
  /** Active warning count for the row. */
  warningCount: number;
  /** Replay highlight, or ``null`` when not in replay focus. */
  replay: TimelineRowReplayMark | null;
  /** Coroutine name, or ``null``. */
  coroutineName: string | null;
  /** Stable monotonic create time in ns — used by ordering tie-breakers. */
  createdAtMonotonicNs: number;
}

/** Canonical row projection — output of :func:`projectTimelineRows`. */
export interface TimelineRowProjection {
  /** Rows in deterministic order, indexed by ``rowIndex``. */
  rows: readonly TimelineRowProjectionEntry[];
  /** Stable lookup from ``rowId`` → ``rowIndex``. */
  rowIndexByRowId: ReadonlyMap<string, number>;
  /** Stable lookup from ``taskId`` → ``rowId``. */
  rowIdByTaskId: ReadonlyMap<string, string>;
  /** Sequence cursor when the projection was built. */
  sequence: number;
  /** Total number of rows; redundant convenience field. */
  totalRows: number;
}

/** Sentinel projection used by hooks before data hydrates. */
export const EMPTY_TIMELINE_ROW_PROJECTION: TimelineRowProjection = Object.freeze({
  rows: Object.freeze([]) as readonly TimelineRowProjectionEntry[],
  rowIndexByRowId: new Map(),
  rowIdByTaskId: new Map(),
  sequence: 0,
  totalRows: 0,
});
