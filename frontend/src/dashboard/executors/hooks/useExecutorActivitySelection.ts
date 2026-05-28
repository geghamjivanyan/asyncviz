/**
 * Selection hook for the executor activity panel.
 *
 * Executors don't directly correspond to tasks (a single executor
 * runs work submitted by many tasks), so the inspector-reveal here
 * accepts an optional ``taskId`` for cases where the caller has a
 * specific submitting-task context (e.g. clicked from a dependency
 * graph edge into a specific work item).
 */

import { useCallback } from "react";
import { useRuntimeStore } from "@/state/runtime";
import { useExecutorActivityStore } from "@/dashboard/executors/ExecutorActivityStore";
import { getExecutorActivityPanelMetrics } from "@/dashboard/executors/diagnostics/ExecutorActivityMetricsCollector";
import { recordExecutorActivityTrace } from "@/dashboard/executors/diagnostics/ExecutorActivityTracing";

export interface UseExecutorActivitySelectionResult {
  selectedExecutorId: string | null;
  selectExecutor: (executorId: string | null) => void;
  revealExecutor: (
    executorId: string,
    options?: { taskId?: string | null },
  ) => boolean;
}

export function useExecutorActivitySelection(): UseExecutorActivitySelectionResult {
  const selectedExecutorId = useExecutorActivityStore((s) => s.selectedExecutorId);
  const setSelectedExecutor = useExecutorActivityStore((s) => s.setSelectedExecutor);
  const selectTask = useRuntimeStore((s) => s.selectTask);

  const selectExecutor = useCallback(
    (executorId: string | null) => {
      setSelectedExecutor(executorId);
      getExecutorActivityPanelMetrics().recordSelectionChange();
      recordExecutorActivityTrace({
        kind: "selection-changed",
        detail: executorId ?? "(none)",
      });
    },
    [setSelectedExecutor],
  );

  const revealExecutor = useCallback(
    (executorId: string, options?: { taskId?: string | null }) => {
      setSelectedExecutor(executorId);
      getExecutorActivityPanelMetrics().recordSelectionChange();
      const taskId = options?.taskId ?? null;
      if (taskId !== null && taskId !== "") {
        selectTask(taskId);
        getExecutorActivityPanelMetrics().recordInspectorReveal();
        recordExecutorActivityTrace({
          kind: "inspector-revealed",
          detail: `executor=${executorId} task=${taskId}`,
        });
        return true;
      }
      recordExecutorActivityTrace({
        kind: "selection-changed",
        detail: executorId,
      });
      return false;
    },
    [setSelectedExecutor, selectTask],
  );

  return { selectedExecutorId, selectExecutor, revealExecutor };
}
