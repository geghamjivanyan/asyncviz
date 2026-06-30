/**
 * Selection + inspector-reveal hook for the semaphore panel.
 *
 * Selection state lives on :class:`SemaphoreContentionStore`. The
 * ``revealSemaphore`` helper additionally nudges the global
 * ``selectedTaskId`` when a correlated task id is supplied, so the
 * existing ``TaskInspector`` surface lights up without a dedicated
 * semaphore inspector.
 */

import { useCallback } from "react";
import { useRuntimeStore } from "@/state/runtime";
import { useSemaphoreContentionStore } from "@/dashboard/semaphores/SemaphoreContentionStore";
import { getSemaphoreContentionPanelMetrics } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionMetricsCollector";
import { recordSemaphoreContentionTrace } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionTracing";

export interface UseSemaphoreContentionSelectionResult {
  selectedSemaphoreId: string | null;
  selectSemaphore: (semaphoreId: string | null) => void;
  revealSemaphore: (semaphoreId: string, options?: { taskId?: string | null }) => boolean;
}

export function useSemaphoreContentionSelection(): UseSemaphoreContentionSelectionResult {
  const selectedSemaphoreId = useSemaphoreContentionStore((s) => s.selectedSemaphoreId);
  const setSelectedSemaphore = useSemaphoreContentionStore((s) => s.setSelectedSemaphore);
  const selectTask = useRuntimeStore((s) => s.selectTask);

  const selectSemaphore = useCallback(
    (semaphoreId: string | null) => {
      setSelectedSemaphore(semaphoreId);
      getSemaphoreContentionPanelMetrics().recordSelectionChange();
      recordSemaphoreContentionTrace({
        kind: "selection-changed",
        detail: semaphoreId ?? "(none)",
      });
    },
    [setSelectedSemaphore],
  );

  const revealSemaphore = useCallback(
    (semaphoreId: string, options?: { taskId?: string | null }) => {
      setSelectedSemaphore(semaphoreId);
      getSemaphoreContentionPanelMetrics().recordSelectionChange();
      const taskId = options?.taskId ?? null;
      if (taskId !== null && taskId !== "") {
        selectTask(taskId);
        getSemaphoreContentionPanelMetrics().recordInspectorReveal();
        recordSemaphoreContentionTrace({
          kind: "inspector-revealed",
          detail: `semaphore=${semaphoreId} task=${taskId}`,
        });
        return true;
      }
      recordSemaphoreContentionTrace({
        kind: "selection-changed",
        detail: semaphoreId,
      });
      return false;
    },
    [setSelectedSemaphore, selectTask],
  );

  return { selectedSemaphoreId, selectSemaphore, revealSemaphore };
}
