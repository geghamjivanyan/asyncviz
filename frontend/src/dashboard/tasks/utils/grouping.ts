/**
 * Helpers for grouping warnings + segments by task id.
 *
 * The store keeps warnings under a single index and segments under
 * a per-task list; the table needs O(1) lookups when projecting rows.
 * The grouping helpers convert the store state into row-friendly
 * maps. They're written as pure functions so memoization is trivial.
 */

import type { ActiveWarning, TaskSnapshot } from "@/types/runtime";

export function groupWarningsByTask(
  warnings: readonly ActiveWarning[],
): Record<string, ActiveWarning[]> {
  const out: Record<string, ActiveWarning[]> = {};
  for (const warning of warnings) {
    for (const taskId of warning.related_task_ids ?? []) {
      const bucket = out[taskId] ?? [];
      bucket.push(warning);
      out[taskId] = bucket;
    }
  }
  return out;
}

export function buildParentExistsSet(tasksById: Record<string, TaskSnapshot>): Set<string> {
  return new Set(Object.keys(tasksById));
}

const EMPTY_WARNINGS: readonly ActiveWarning[] = [];

export function warningsForTask(
  index: Record<string, ActiveWarning[]>,
  taskId: string,
): readonly ActiveWarning[] {
  return index[taskId] ?? EMPTY_WARNINGS;
}
