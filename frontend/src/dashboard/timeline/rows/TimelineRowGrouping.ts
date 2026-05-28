/**
 * Row grouping foundations.
 *
 * Today every task gets its own row; tomorrow we will collapse rows
 * by lineage root, coroutine name, or runtime id. The grouping module
 * captures that future-facing structure without implementing the full
 * collapse-aware renderer yet.
 *
 * The current implementation:
 *
 *   * exposes a deterministic flat grouping (one group per row) so
 *     downstream code already speaks the group language,
 *   * supplies a pure helper to fold rows into root-id groups for
 *     diagnostics + tests that exercise the future shape,
 *   * is the home for collapse / expand state once we wire interaction.
 */

import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";

export interface TimelineRowGroup {
  /** Stable group id (lineage root id today). */
  groupId: string;
  /** Display label — falls back to the first row's label. */
  label: string;
  /** Member rows in stable order. */
  rows: readonly TimelineRowProjectionEntry[];
  /** ``true`` when the group is currently collapsed. */
  collapsed: boolean;
}

export interface TimelineRowGrouping {
  groups: readonly TimelineRowGroup[];
  /** ``true`` when grouping is the no-op flat grouping. */
  flat: boolean;
}

/** Pure: every row in its own group. Today's default. */
export function flatGrouping(rows: readonly TimelineRowProjectionEntry[]): TimelineRowGrouping {
  const groups: TimelineRowGroup[] = rows.map((row) => ({
    groupId: row.rowId,
    label: row.label,
    rows: [row],
    collapsed: false,
  }));
  return { groups, flat: true };
}

/** Pure: fold rows by lineage root id. Used by debugging tools today. */
export function groupByLineageRoot(
  rows: readonly TimelineRowProjectionEntry[],
): TimelineRowGrouping {
  const buckets = new Map<string, TimelineRowProjectionEntry[]>();
  for (const row of rows) {
    const rootId = row.parentTaskId ?? row.taskId;
    const bucket = buckets.get(rootId);
    if (bucket === undefined) {
      buckets.set(rootId, [row]);
    } else {
      bucket.push(row);
    }
  }
  const groups: TimelineRowGroup[] = [];
  for (const [groupId, members] of buckets.entries()) {
    members.sort((a, b) => a.rowIndex - b.rowIndex);
    const first = members[0];
    groups.push({
      groupId,
      label: first?.label ?? groupId,
      rows: members,
      collapsed: false,
    });
  }
  groups.sort((a, b) => (a.rows[0]?.rowIndex ?? 0) - (b.rows[0]?.rowIndex ?? 0));
  return { groups, flat: false };
}
