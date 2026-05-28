/**
 * Helpers that produce row-scope invalidation events.
 *
 * Keeping the row-scope helpers separate makes call sites readable
 * (``invalidateRow.add(tracker, "task-1", { sequence: 12 })``) without
 * exposing the raw :class:`TimelineInvalidationTracker` push surface.
 */

import type { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";

export function invalidateRow(
  tracker: TimelineInvalidationTracker,
  taskId: string,
  options: { sequence?: number | null; atMs?: number } = {},
): void {
  tracker.push({
    reason: "row",
    taskIds: [taskId],
    sequence: options.sequence ?? null,
    atMs: options.atMs,
  });
}

export function invalidateRows(
  tracker: TimelineInvalidationTracker,
  taskIds: readonly string[],
  options: { sequence?: number | null; atMs?: number } = {},
): void {
  if (taskIds.length === 0) return;
  tracker.push({
    reason: "row",
    taskIds,
    sequence: options.sequence ?? null,
    atMs: options.atMs,
  });
}
