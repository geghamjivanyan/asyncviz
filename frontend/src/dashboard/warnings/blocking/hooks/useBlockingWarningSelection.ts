/**
 * Selection hook.
 *
 * Tracks the currently focused warning group via the store, with a
 * stable action callback so the panel + inspector don't recreate it
 * each render.
 */

import { useCallback } from "react";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import { recordBlockingWarningTrace } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";
import { getBlockingWarningPanelMetrics } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";

export function useBlockingWarningSelection(): {
  selectedGroupId: string | null;
  selectGroup: (groupId: string | null) => void;
  clearSelection: () => void;
} {
  const selectedGroupId = useBlockingWarningStore((s) => s.selectedGroupId);
  const setSelectedGroup = useBlockingWarningStore((s) => s.setSelectedGroup);

  const selectGroup = useCallback(
    (groupId: string | null) => {
      setSelectedGroup(groupId);
      getBlockingWarningPanelMetrics().recordSelectionChange();
      recordBlockingWarningTrace({
        kind: "selection-changed",
        detail: groupId ?? "<cleared>",
      });
    },
    [setSelectedGroup],
  );

  const clearSelection = useCallback(() => {
    selectGroup(null);
  }, [selectGroup]);

  return { selectedGroupId, selectGroup, clearSelection };
}
