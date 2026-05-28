/**
 * Zustand-backed selectors that surface every slice the inspector
 * panels consume.
 *
 * The selectors are intentionally narrow — each pulls one store
 * slice + memoizes a small derivation. The container composes them
 * into a single :type:`TaskInspection`.
 */

import { useMemo } from "react";
import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskSnapshot,
  TaskTransitionRecord,
  TimelineSegment,
} from "@/types/runtime";
import { useRuntimeStore } from "@/state/runtime";

/** Snapshot of the selected task, or ``null``. */
export function useSelectedTaskSnapshot(): TaskSnapshot | null {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const tasksById = useRuntimeStore((s) => s.tasksById);
  return useMemo(() => (id === null ? null : (tasksById[id] ?? null)), [id, tasksById]);
}

/** Stable list of closed segments for the selected task. */
export function useSelectedTaskSegments(): readonly TimelineSegment[] {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const segmentIds = useRuntimeStore((s) => s.timeline.segmentIdsByTaskId);
  const segments = useRuntimeStore((s) => s.timeline.segmentsById);
  return useMemo(() => {
    if (id === null) return [];
    const ids = segmentIds[id] ?? [];
    const list: TimelineSegment[] = [];
    for (const segmentId of ids) {
      const segment = segments[segmentId];
      if (segment !== undefined) list.push(segment);
    }
    list.sort((a, b) => a.monotonic_start_ns - b.monotonic_start_ns);
    return list;
  }, [id, segmentIds, segments]);
}

/** Optional active (still-running) segment for the selected task. */
export function useSelectedTaskActiveSegment(): ActiveTimelineSegment | null {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const active = useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
  return useMemo(() => (id === null ? null : (active[id] ?? null)), [id, active]);
}

/** Active warnings whose ``related_task_ids`` include the selected
 *  task. */
export function useSelectedTaskWarnings(): readonly ActiveWarning[] {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const warningsById = useRuntimeStore((s) => s.warnings.warningsById);
  const activeIds = useRuntimeStore((s) => s.warnings.activeWarningIds);
  return useMemo(() => {
    if (id === null) return [];
    const out: ActiveWarning[] = [];
    for (const warningId of activeIds) {
      const warning = warningsById[warningId];
      if (warning === undefined) continue;
      if (warning.resolved || warning.expired) continue;
      if (warning.related_task_ids.includes(id)) out.push(warning);
    }
    return out;
  }, [id, warningsById, activeIds]);
}

/** Child task ids for the selected task. */
export function useSelectedTaskChildren(): readonly string[] {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const tasksById = useRuntimeStore((s) => s.tasksById);
  return useMemo(() => {
    if (id === null) return [];
    const children: string[] = [];
    for (const task of Object.values(tasksById)) {
      if (task.parent_task_id === id) children.push(task.task_id);
    }
    children.sort();
    return children;
  }, [id, tasksById]);
}

/** Sibling count for the selected task — tasks sharing the same
 *  parent (excluding the selected task itself). */
export function useSelectedTaskSiblingCount(): number {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const tasksById = useRuntimeStore((s) => s.tasksById);
  return useMemo(() => {
    if (id === null) return 0;
    const self = tasksById[id];
    if (self === undefined || self.parent_task_id === null) return 0;
    let count = 0;
    for (const task of Object.values(tasksById)) {
      if (task.task_id === id) continue;
      if (task.parent_task_id === self.parent_task_id) count += 1;
    }
    return count;
  }, [id, tasksById]);
}

/** Recent runtime events scoped to the selected task. Returns ``[]``
 *  when the store doesn't carry events for the task. */
export function useSelectedTaskEvents(): ReadonlyArray<{
  event_id: string;
  event_type: string;
  monotonic_ns: number;
  task_id: string;
}> {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const events = useRuntimeStore((s) => s.events);
  return useMemo(() => {
    if (id === null) return [];
    return events.filter((event) => event.task_id === id);
  }, [id, events]);
}

/** Lifecycle transitions for the selected task — the store mirrors
 *  these in ``state.transitions`` when the backend ships them. */
export function useSelectedTaskTransitions(): readonly TaskTransitionRecord[] {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const tasksById = useRuntimeStore((s) => s.tasksById);
  // Reserved for the future state-snapshot wire-up — today the
  // snapshot's ``transitions`` map isn't normalized into the store,
  // so we surface an empty list and let the panel render a "no
  // transitions" hint. Keeping the hook stable today means future
  // store work doesn't need to refactor callers.
  void tasksById;
  void id;
  return useMemo(() => [] as readonly TaskTransitionRecord[], []);
}

/** Replay metadata snapshot. */
export function useReplayMetaSummary(): {
  oldestRetainedSequence: number | null;
  newestRetainedSequence: number | null;
  windowHit: boolean;
  lastSequence: number;
} {
  const replay = useRuntimeStore((s) => s.replay);
  const lastSequence = useRuntimeStore((s) => s.lastSequence);
  return useMemo(
    () => ({
      oldestRetainedSequence: replay.oldestRetainedSequence,
      newestRetainedSequence: replay.newestRetainedSequence,
      windowHit: replay.windowHit,
      lastSequence,
    }),
    [replay, lastSequence],
  );
}

/** Optional aggregator-side coroutine throughput, scoped to the
 *  selected task's coroutine name. */
export function useSelectedTaskCoroutineThroughput(): number | null {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const tasksById = useRuntimeStore((s) => s.tasksById);
  const aggregate = useRuntimeStore((s) => s.metrics.aggregate);
  return useMemo(() => {
    if (id === null || aggregate === null) return null;
    const task = tasksById[id];
    if (task === undefined || task.coroutine_name === null) return null;
    for (const row of aggregate.coroutines) {
      if (row.coroutine_name === task.coroutine_name) {
        return row.completed_avg_duration_seconds === null
          ? null
          : 1 / Math.max(0.0001, row.completed_avg_duration_seconds);
      }
    }
    return null;
  }, [id, tasksById, aggregate]);
}
