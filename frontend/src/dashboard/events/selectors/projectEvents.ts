/**
 * Pure projection: store state → :type:`EventRow` array.
 *
 * The projection is exposed as a pure function so:
 *
 *   * It can be tested without React / Zustand.
 *   * Memoization is straightforward — callers pass the same input
 *     references, get the same output array reference back.
 *
 * Runtime fields are pulled from the canonical normalized projections
 * the runtime store maintains. The function does *not* look at the
 * store directly — that's the caller hook's responsibility.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskLifecycleEvent,
  TaskSnapshot,
} from "@/types/runtime";
import { buildEventRow, type EventRow, type EventSource } from "@/dashboard/events/models/eventRow";

export interface EventProjectionInputs {
  events: readonly TaskLifecycleEvent[];
  tasksById: Record<string, TaskSnapshot>;
  activeWarnings: readonly ActiveWarning[];
  activeSegmentsByTaskId: Record<string, ActiveTimelineSegment>;
  /** Optional set of event ids known to come from a replay batch. */
  replayEventIds?: ReadonlySet<string>;
}

function groupWarningsByTask(warnings: readonly ActiveWarning[]): Record<string, ActiveWarning[]> {
  const out: Record<string, ActiveWarning[]> = {};
  for (const w of warnings) {
    for (const taskId of w.related_task_ids ?? []) {
      const bucket = out[taskId] ?? [];
      bucket.push(w);
      out[taskId] = bucket;
    }
  }
  return out;
}

const EMPTY_WARNINGS: readonly ActiveWarning[] = [];

export function projectEventRows(inputs: EventProjectionInputs): EventRow[] {
  if (inputs.events.length === 0) return [];
  const warningsByTask = groupWarningsByTask(inputs.activeWarnings);
  const replayIds = inputs.replayEventIds ?? new Set<string>();
  const rows: EventRow[] = new Array(inputs.events.length);
  for (let i = 0; i < inputs.events.length; i += 1) {
    const event = inputs.events[i]!;
    const warningsForTask = warningsByTask[event.task_id] ?? EMPTY_WARNINGS;
    const hasActiveSegment = inputs.activeSegmentsByTaskId[event.task_id] !== undefined;
    const taskKnown = inputs.tasksById[event.task_id] !== undefined;
    const source: EventSource = replayIds.has(event.event_id) ? "replay" : "live";
    rows[i] = buildEventRow({
      event,
      warningsForTask,
      taskKnown,
      hasActiveSegment,
      source,
    });
  }
  return rows;
}
