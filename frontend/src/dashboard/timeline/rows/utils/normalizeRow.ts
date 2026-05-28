/**
 * Pure helper — coerce a (possibly minimal) :type:`TimelineRow` into a
 * fully-populated :type:`TimelineRowProjectionEntry`. The scene graph
 * passes rich rows when projections come from the rows package, but
 * tests + legacy callers may push sparse rows; this helper keeps the
 * row layer dependency-tolerant.
 */

import type {
  TimelineRow,
  TimelineRowState,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";

const KNOWN_STATES = new Set<TimelineRowState>([
  "created",
  "running",
  "waiting",
  "completed",
  "cancelled",
  "failed",
  "unknown",
]);

export function normalizeRow(row: TimelineRow): TimelineRowProjectionEntry {
  const state =
    row.state !== undefined && KNOWN_STATES.has(row.state) ? row.state : "unknown";
  return {
    rowIndex: row.rowIndex,
    rowId: row.taskId,
    taskId: row.taskId,
    label: row.label,
    coroutineName: row.coroutineName ?? null,
    state,
    parentTaskId: row.parentTaskId ?? null,
    depth: row.depth ?? 0,
    childCount: row.childCount ?? 0,
    warningSeverity: row.warningSeverity ?? null,
    warningCount: row.warningCount ?? 0,
    replay: row.replay ?? null,
    createdAtMonotonicNs: row.createdAtMonotonicNs ?? 0,
  };
}
