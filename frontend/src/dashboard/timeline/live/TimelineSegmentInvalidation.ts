/**
 * Helpers that produce segment-scope invalidation events.
 */

import type { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";

export function invalidateSegment(
  tracker: TimelineInvalidationTracker,
  segmentId: string,
  taskId?: string,
  options: { sequence?: number | null; atMs?: number } = {},
): void {
  tracker.push({
    reason: "segment",
    taskIds: taskId !== undefined ? [taskId] : undefined,
    segmentIds: [segmentId],
    sequence: options.sequence ?? null,
    atMs: options.atMs,
  });
}

export function invalidateSegments(
  tracker: TimelineInvalidationTracker,
  segmentIds: readonly string[],
  taskIds: readonly string[] | undefined,
  options: { sequence?: number | null; atMs?: number } = {},
): void {
  if (segmentIds.length === 0 && (taskIds === undefined || taskIds.length === 0)) return;
  tracker.push({
    reason: "segment",
    taskIds,
    segmentIds,
    sequence: options.sequence ?? null,
    atMs: options.atMs,
  });
}
