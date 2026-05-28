/**
 * Memoization-friendly selectors for the runtime store.
 *
 * Selectors here return either primitives or references — Zustand's
 * shallow equality check picks up changes correctly. Projections that
 * derive new arrays (e.g. ``selectActiveTasks``) call ``map`` over the
 * id index so the returned array changes identity only when the
 * underlying ids change, not on every render.
 */

import { useMemo } from "react";
import type { ActiveWarning, TaskLifecycleState, TaskSnapshot } from "@/types/runtime";
import { useRuntimeStore } from "@/state/runtime/store";

// ── Primitive selectors (no derivation) ──────────────────────────

export function useConnectionPhase() {
  return useRuntimeStore((s) => s.connection.phase);
}

export function useConnectionState() {
  return useRuntimeStore((s) => s.connection.state);
}

export function useRuntimeStatus() {
  return useRuntimeStore((s) => s.runtime.status);
}

export function useLastSequence() {
  return useRuntimeStore((s) => s.lastSequence);
}

export function useServerUptimeSeconds() {
  return useRuntimeStore((s) => s.runtime.serverUptimeSeconds);
}

export function useConnectedClients() {
  return useRuntimeStore((s) => s.runtime.connectedClients);
}

export function useSelectedTaskId() {
  return useRuntimeStore((s) => s.selectedTaskId);
}

export function useTasksById() {
  return useRuntimeStore((s) => s.tasksById);
}

export function useEvents() {
  return useRuntimeStore((s) => s.events);
}

export function useReconciliationStats() {
  return useRuntimeStore((s) => s.stats);
}

// ── Derived projections (memoized at call site) ───────────────────

/** Stable list of tasks in a given state — re-computes only when the
 *  id index changes. */
export function useTasksInState(state: TaskLifecycleState): TaskSnapshot[] {
  const tasksById = useRuntimeStore((s) => s.tasksById);
  const ids = useRuntimeStore((s) => s.taskIdsByState[state]);
  return useMemo(
    () => ids.map((id) => tasksById[id]).filter((task): task is TaskSnapshot => task !== undefined),
    [tasksById, ids],
  );
}

/** Returns the currently selected task snapshot, or ``undefined``. */
export function useSelectedTask(): TaskSnapshot | undefined {
  const id = useRuntimeStore((s) => s.selectedTaskId);
  const tasksById = useRuntimeStore((s) => s.tasksById);
  return id === null ? undefined : tasksById[id];
}

/** The set of currently-active warnings, materialized from the id index. */
export function useActiveWarnings(): ActiveWarning[] {
  const warningsById = useRuntimeStore((s) => s.warnings.warningsById);
  const ids = useRuntimeStore((s) => s.warnings.activeWarningIds);
  return useMemo(
    () =>
      ids
        .map((id) => warningsById[id])
        .filter((warning): warning is ActiveWarning => warning !== undefined),
    [warningsById, ids],
  );
}

/** Counts of warnings by severity (already materialized in the store). */
export function useWarningSeverityCounts() {
  return useRuntimeStore((s) => s.warnings.countsBySeverity);
}

/** Map of taskId → active timeline segment. */
export function useActiveTimelineSegments() {
  return useRuntimeStore((s) => s.timeline.activeSegmentsByTaskId);
}

/** Closed timeline segments for one task, oldest first. */
export function useTimelineSegmentsForTask(taskId: string | null) {
  const segmentsById = useRuntimeStore((s) => s.timeline.segmentsById);
  const segmentIdsByTaskId = useRuntimeStore((s) => s.timeline.segmentIdsByTaskId);
  return useMemo(() => {
    if (taskId === null) return [];
    const ids = segmentIdsByTaskId[taskId] ?? [];
    return ids.map((id) => segmentsById[id]).filter((s) => s !== undefined);
  }, [taskId, segmentsById, segmentIdsByTaskId]);
}

/** Aggregate metrics snapshot from the most recent hydration. */
export function useMetricsAggregate() {
  return useRuntimeStore((s) => s.metrics.aggregate);
}

/** Rolling delta counts since the last hydration. */
export function useMetricsDeltaCounts() {
  return useRuntimeStore((s) => s.metrics.deltaCounts);
}

/** Replay metadata — the window the backend can still satisfy. */
export function useReplayMeta() {
  return useRuntimeStore((s) => s.replay);
}

/** Runtime metadata — id, clock, server uptime, connected clients. */
export function useRuntimeMeta() {
  return useRuntimeStore((s) => s.runtime);
}
