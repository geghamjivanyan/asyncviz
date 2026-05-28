/**
 * Selection + inspector-reveal hook for the queue panel.
 *
 * The selection state lives on :class:`QueuePressureStore`; this hook
 * exposes selection + reveal callbacks that components can wire to
 * card clicks, marker activations, and keyboard navigation.
 *
 * When a queue is focused with associated correlated tasks, the hook
 * also calls into :func:`useRuntimeStore` to nudge the global selected
 * task — letting the existing :class:`TaskInspector` surface render
 * the task context without a dedicated queue inspector.
 */

import { useCallback } from "react";
import { useRuntimeStore } from "@/state/runtime";
import { useQueuePressureStore } from "@/dashboard/queues/QueuePressureStore";
import { getQueuePressurePanelMetrics } from "@/dashboard/queues/diagnostics/QueuePressureMetricsCollector";
import { recordQueuePressureTrace } from "@/dashboard/queues/diagnostics/QueuePressureTracing";

export interface UseQueuePressureSelectionResult {
  selectedQueueId: string | null;
  selectQueue: (queueId: string | null) => void;
  /**
   * Reveal the queue in any side surface (currently the task inspector
   * if the queue carries a correlated task id). Returns ``true`` if a
   * downstream reveal action fired so callers can chain announcements.
   */
  revealQueue: (queueId: string, options?: { taskId?: string | null }) => boolean;
}

export function useQueuePressureSelection(): UseQueuePressureSelectionResult {
  const selectedQueueId = useQueuePressureStore((s) => s.selectedQueueId);
  const setSelectedQueue = useQueuePressureStore((s) => s.setSelectedQueue);
  const selectTask = useRuntimeStore((s) => s.selectTask);

  const selectQueue = useCallback(
    (queueId: string | null) => {
      setSelectedQueue(queueId);
      getQueuePressurePanelMetrics().recordSelectionChange();
      recordQueuePressureTrace({
        kind: "selection-changed",
        detail: queueId ?? "(none)",
      });
    },
    [setSelectedQueue],
  );

  const revealQueue = useCallback(
    (queueId: string, options?: { taskId?: string | null }) => {
      setSelectedQueue(queueId);
      getQueuePressurePanelMetrics().recordSelectionChange();
      const taskId = options?.taskId ?? null;
      if (taskId !== null && taskId !== "") {
        selectTask(taskId);
        getQueuePressurePanelMetrics().recordInspectorReveal();
        recordQueuePressureTrace({
          kind: "inspector-revealed",
          detail: `queue=${queueId} task=${taskId}`,
        });
        return true;
      }
      recordQueuePressureTrace({
        kind: "selection-changed",
        detail: queueId,
      });
      return false;
    },
    [setSelectedQueue, selectTask],
  );

  return { selectedQueueId, selectQueue, revealQueue };
}
