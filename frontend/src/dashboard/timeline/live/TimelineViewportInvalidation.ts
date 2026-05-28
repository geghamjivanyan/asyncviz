/**
 * Helpers that produce viewport-scope invalidation events.
 *
 * The viewport invalidation is the heaviest hammer: it tells the
 * renderer to recompute culling for the entire scene. Use it when
 * the camera, canvas size, device pixel ratio, or label-column width
 * changes.
 */

import type { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";

export function invalidateViewport(
  tracker: TimelineInvalidationTracker,
  options: { sequence?: number | null; atMs?: number } = {},
): void {
  tracker.push({
    reason: "viewport",
    sequence: options.sequence ?? null,
    atMs: options.atMs,
  });
}

export function invalidateSelection(
  tracker: TimelineInvalidationTracker,
  options: { sequence?: number | null; atMs?: number } = {},
): void {
  tracker.push({
    reason: "selection",
    sequence: options.sequence ?? null,
    atMs: options.atMs,
  });
}

export function invalidateWarnings(
  tracker: TimelineInvalidationTracker,
  taskIds: readonly string[] = [],
  options: { sequence?: number | null; atMs?: number } = {},
): void {
  tracker.push({
    reason: "warning",
    taskIds: taskIds.length > 0 ? taskIds : undefined,
    sequence: options.sequence ?? null,
    atMs: options.atMs,
  });
}
