/**
 * Segment grouping foundations.
 *
 * Today every segment belongs to a single row and renders as a flat
 * bar. The grouping module captures the future-facing shape used by
 * flamegraph + nested-span rendering without implementing the full
 * stacked renderer yet:
 *
 *   * deterministic "flat" grouping (one entry per group),
 *   * pure helper to fold entries by their owning task (collapse all
 *     segments for a task into a single group — useful for the
 *     debugger's "show task" view),
 *   * pure helper to fold entries by lineage parent (collapse a
 *     parent's segments + its descendants into a single group).
 */

import type { TimelineSegmentProjectionEntry } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";

export interface TimelineSegmentGroup {
  /** Stable group id (segmentId for flat, taskId for by-task, etc.). */
  groupId: string;
  /** Member entries in stable order. */
  entries: readonly TimelineSegmentProjectionEntry[];
  /** Earliest start time across the group. */
  earliestStartSeconds: number;
  /** Latest end time across the group. */
  latestEndSeconds: number;
  /** ``true`` when the group contains at least one active segment. */
  hasActive: boolean;
}

export interface TimelineSegmentGrouping {
  groups: readonly TimelineSegmentGroup[];
  /** ``true`` when grouping is the no-op flat grouping. */
  flat: boolean;
}

export function flatGrouping(
  entries: readonly TimelineSegmentProjectionEntry[],
): TimelineSegmentGrouping {
  const groups: TimelineSegmentGroup[] = entries.map((entry) => ({
    groupId: entry.segmentId,
    entries: [entry],
    earliestStartSeconds: entry.startSeconds,
    latestEndSeconds: entry.endSeconds,
    hasActive: entry.isActive,
  }));
  return { groups, flat: true };
}

export function groupByTask(
  entries: readonly TimelineSegmentProjectionEntry[],
): TimelineSegmentGrouping {
  return groupBy(entries, (entry) => entry.taskId);
}

export function groupByLineageParent(
  entries: readonly TimelineSegmentProjectionEntry[],
): TimelineSegmentGrouping {
  return groupBy(entries, (entry) => entry.parentTaskId ?? entry.taskId);
}

function groupBy(
  entries: readonly TimelineSegmentProjectionEntry[],
  keyFn: (entry: TimelineSegmentProjectionEntry) => string,
): TimelineSegmentGrouping {
  const buckets = new Map<string, TimelineSegmentProjectionEntry[]>();
  for (const entry of entries) {
    const key = keyFn(entry);
    const bucket = buckets.get(key);
    if (bucket === undefined) buckets.set(key, [entry]);
    else bucket.push(entry);
  }
  const groups: TimelineSegmentGroup[] = [];
  for (const [groupId, members] of buckets.entries()) {
    members.sort((a, b) => a.startSeconds - b.startSeconds);
    let earliest = Number.POSITIVE_INFINITY;
    let latest = Number.NEGATIVE_INFINITY;
    let hasActive = false;
    for (const entry of members) {
      if (entry.startSeconds < earliest) earliest = entry.startSeconds;
      if (entry.endSeconds > latest) latest = entry.endSeconds;
      if (entry.isActive) hasActive = true;
    }
    groups.push({
      groupId,
      entries: members,
      earliestStartSeconds: Number.isFinite(earliest) ? earliest : 0,
      latestEndSeconds: Number.isFinite(latest) ? latest : 0,
      hasActive,
    });
  }
  groups.sort((a, b) => a.earliestStartSeconds - b.earliestStartSeconds);
  return { groups, flat: false };
}
