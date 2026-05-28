/**
 * Canonical React hook that builds a :type:`TaskInspection` for the
 * currently-selected task.
 *
 * The hook composes every store selector + the pure projection
 * helper into one memoized snapshot the panels consume.
 */

import { useMemo, useRef } from "react";
import {
  buildTaskInspection,
} from "@/dashboard/inspector/selectors/inspectionSelectors";
import {
  useReplayMetaSummary,
  useSelectedTaskActiveSegment,
  useSelectedTaskChildren,
  useSelectedTaskCoroutineThroughput,
  useSelectedTaskSegments,
  useSelectedTaskSiblingCount,
  useSelectedTaskSnapshot,
  useSelectedTaskTransitions,
  useSelectedTaskWarnings,
} from "@/dashboard/inspector/selectors/storeInspectionSelectors";
import {
  getTimelineInspectorMetrics,
} from "@/dashboard/inspector/TaskInspectorMetricsCollector";
import { traceInspectorProjection } from "@/dashboard/inspector/TaskInspectorTracing";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export function useTaskInspection(): TaskInspection {
  const task = useSelectedTaskSnapshot();
  const segments = useSelectedTaskSegments();
  const activeSegment = useSelectedTaskActiveSegment();
  const activeWarnings = useSelectedTaskWarnings();
  const childTaskIds = useSelectedTaskChildren();
  const siblingCount = useSelectedTaskSiblingCount();
  const replay = useReplayMetaSummary();
  const coroutineThroughputPerSecond = useSelectedTaskCoroutineThroughput();
  const transitions = useSelectedTaskTransitions();
  const generationRef = useRef(0);

  return useMemo(() => {
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    generationRef.current += 1;
    const inspection = buildTaskInspection({
      task,
      transitions,
      segments,
      activeSegment,
      activeWarnings,
      childTaskIds,
      siblingCount,
      coroutineThroughputPerSecond,
      replay,
      generation: generationRef.current,
    });
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    getTimelineInspectorMetrics().recordProjection(end - start);
    traceInspectorProjection(
      `task=${task?.task_id ?? "null"} gen=${inspection.generation} duration=${(end - start).toFixed(3)}ms`,
    );
    return inspection;
  }, [
    task,
    transitions,
    segments,
    activeSegment,
    activeWarnings,
    childTaskIds,
    siblingCount,
    coroutineThroughputPerSecond,
    replay,
  ]);
}
