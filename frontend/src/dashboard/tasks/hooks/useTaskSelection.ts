/**
 * Selection plumbing — wraps the canonical store's selection API so
 * the table doesn't reach into ``useRuntimeStore`` directly.
 *
 * Selection is stored in the runtime store so the inspector / future
 * timeline-focus / future debugger all observe the same id.
 */

import { useCallback } from "react";
import { useRuntimeStore } from "@/state/runtime/store";
import { useSelectedTaskId } from "@/state/runtime/selectors";
import { getTaskTableMetrics } from "@/dashboard/tasks/observability/tableMetrics";

export interface TaskSelectionValue {
  selectedTaskId: string | null;
  selectTask: (taskId: string | null) => void;
  isSelected: (taskId: string) => boolean;
}

export function useTaskSelection(): TaskSelectionValue {
  const selectedTaskId = useSelectedTaskId();
  const storeSelect = useRuntimeStore((s) => s.selectTask);
  const selectTask = useCallback(
    (taskId: string | null) => {
      getTaskTableMetrics().recordSelection();
      storeSelect(taskId);
    },
    [storeSelect],
  );
  const isSelected = useCallback((taskId: string) => taskId === selectedTaskId, [selectedTaskId]);
  return { selectedTaskId, selectTask, isSelected };
}
