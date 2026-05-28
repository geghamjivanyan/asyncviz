/**
 * Grouping helpers for the event feed.
 *
 * Today the architecture supports four group modes:
 *
 *   * ``none``         — flat list of rows.
 *   * ``task``         — buckets by ``taskId``.
 *   * ``category``     — buckets by category.
 *   * ``replay-batch`` — buckets contiguous runs of source==="replay".
 *
 * The output shape is *always* a list of groups, so consumers don't
 * branch on the mode. When the mode is ``none`` the result is a
 * single synthetic group containing every row.
 */

import type { EventRow } from "@/dashboard/events/models/eventRow";
import type { EventGroupingMode } from "@/dashboard/events/models/filters";

export interface EventGroup {
  groupId: string;
  /** Pre-formatted label used in the group header (e.g. "task t1", "replay batch"). */
  label: string;
  /** Mode that produced the group. */
  mode: EventGroupingMode;
  /** Rows in the group; same order as the input. */
  rows: readonly EventRow[];
  /** Stable signature of the group's content. */
  signature: string;
}

export function groupEventRows(rows: readonly EventRow[], mode: EventGroupingMode): EventGroup[] {
  switch (mode) {
    case "task":
      return groupBy(
        rows,
        (row) => row.taskId,
        (taskId, items) => ({
          groupId: `task:${taskId}`,
          label: `task ${taskId}`,
          mode,
          rows: items,
          signature: signGroup(items),
        }),
      );
    case "category":
      return groupBy(
        rows,
        (row) => row.category,
        (category, items) => ({
          groupId: `category:${category}`,
          label: `category ${category}`,
          mode,
          rows: items,
          signature: signGroup(items),
        }),
      );
    case "replay-batch": {
      const out: EventGroup[] = [];
      let bucket: EventRow[] = [];
      let prev: EventRow["source"] | null = null;
      for (const row of rows) {
        if (prev !== row.source && bucket.length > 0) {
          out.push(makeRunGroup(bucket, out.length, mode));
          bucket = [];
        }
        bucket.push(row);
        prev = row.source;
      }
      if (bucket.length > 0) out.push(makeRunGroup(bucket, out.length, mode));
      return out;
    }
    case "none":
    default:
      return [
        {
          groupId: "all",
          label: "events",
          mode: "none",
          rows,
          signature: signGroup(rows),
        },
      ];
  }
}

function groupBy(
  rows: readonly EventRow[],
  key: (row: EventRow) => string,
  build: (key: string, items: readonly EventRow[]) => EventGroup,
): EventGroup[] {
  const map = new Map<string, EventRow[]>();
  // Preserve order of first appearance.
  const order: string[] = [];
  for (const row of rows) {
    const k = key(row);
    if (!map.has(k)) {
      map.set(k, []);
      order.push(k);
    }
    map.get(k)!.push(row);
  }
  return order.map((k) => build(k, map.get(k)!));
}

function makeRunGroup(
  bucket: readonly EventRow[],
  index: number,
  mode: EventGroupingMode,
): EventGroup {
  const source = bucket[0]?.source ?? "unknown";
  return {
    groupId: `${source}:${index}`,
    label: source === "replay" ? "replay batch" : "live stream",
    mode,
    rows: bucket,
    signature: signGroup(bucket),
  };
}

function signGroup(rows: readonly EventRow[]): string {
  // Cheap hash — just concat the row signatures' first letter + count.
  return `${rows.length}:${rows.map((r) => r.signature.slice(0, 6)).join(",")}`;
}
