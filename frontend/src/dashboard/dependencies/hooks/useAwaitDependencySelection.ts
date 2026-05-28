/**
 * Selection + inspector-reveal hook for the dependency graph.
 *
 * Graph selection lives on the dependency store. ``revealNode`` also
 * nudges the global ``selectedTaskId`` so the existing ``TaskInspector``
 * lights up when a task node is focused.
 */

import { useCallback } from "react";
import { useRuntimeStore } from "@/state/runtime";
import { useAwaitDependencyStore } from "@/dashboard/dependencies/AwaitDependencyStore";
import { getAwaitDependencyPanelMetrics } from "@/dashboard/dependencies/diagnostics/AwaitDependencyMetricsCollector";
import { recordAwaitDependencyTrace } from "@/dashboard/dependencies/diagnostics/AwaitDependencyTracing";
import type { AwaitNodeKind } from "@/dashboard/dependencies/models/AwaitDependencyModels";

export interface UseAwaitDependencySelectionResult {
  selectedNodeId: string | null;
  selectNode: (id: string | null) => void;
  revealNode: (id: string, kind: AwaitNodeKind) => boolean;
}

export function useAwaitDependencySelection(): UseAwaitDependencySelectionResult {
  const selectedNodeId = useAwaitDependencyStore((s) => s.selectedNodeId);
  const setSelectedNode = useAwaitDependencyStore((s) => s.setSelectedNode);
  const selectTask = useRuntimeStore((s) => s.selectTask);

  const selectNode = useCallback(
    (id: string | null) => {
      setSelectedNode(id);
      getAwaitDependencyPanelMetrics().recordSelectionChange();
      recordAwaitDependencyTrace({
        kind: "selection-changed",
        detail: id ?? "(none)",
      });
    },
    [setSelectedNode],
  );

  const revealNode = useCallback(
    (id: string, kind: AwaitNodeKind) => {
      setSelectedNode(id);
      getAwaitDependencyPanelMetrics().recordSelectionChange();
      if (kind === "task") {
        selectTask(id);
        getAwaitDependencyPanelMetrics().recordInspectorReveal();
        recordAwaitDependencyTrace({
          kind: "inspector-revealed",
          detail: `task=${id}`,
        });
        return true;
      }
      recordAwaitDependencyTrace({
        kind: "selection-changed",
        detail: `gather=${id}`,
      });
      return false;
    },
    [setSelectedNode, selectTask],
  );

  return { selectedNodeId, selectNode, revealNode };
}
