/**
 * Store-aware wrapper for the canonical :func:`TaskInspector`.
 *
 * Reads the canonical projection via :func:`useTaskInspection`,
 * owns local panel-selection state, and routes user actions back
 * into the selection store via the canonical
 * :func:`useRuntimeStore` action.
 */

import { useCallback, useState } from "react";
import { useRuntimeStore } from "@/state/runtime";
import { TaskInspector } from "@/dashboard/inspector/TaskInspector";
import { useTaskInspection } from "@/dashboard/inspector/hooks/useTaskInspection";
import { useSelectedTaskEvents } from "@/dashboard/inspector/selectors/storeInspectionSelectors";
import { getTimelineInspectorMetrics } from "@/dashboard/inspector/TaskInspectorMetricsCollector";
import { traceInspectorPanelSwitch } from "@/dashboard/inspector/TaskInspectorTracing";
import type { InspectorPanelKind } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorContainerProps {
  className?: string;
  /** Optional reveal hook — provided by the dashboard so the
   *  inspector's "Fit / Center" buttons can drive the timeline. */
  onRevealSelection?: () => void;
  onFitSelection?: () => void;
}

export function TaskInspectorContainer({
  className,
  onRevealSelection,
  onFitSelection,
}: TaskInspectorContainerProps) {
  const inspection = useTaskInspection();
  const events = useSelectedTaskEvents();
  const storeSelect = useRuntimeStore((s) => s.selectTask);
  const [activePanel, setActivePanelState] = useState<InspectorPanelKind>("overview");

  const onSelectPanel = useCallback((kind: InspectorPanelKind) => {
    setActivePanelState((prev) => {
      if (prev === kind) return prev;
      getTimelineInspectorMetrics().recordPanelSwitch();
      traceInspectorPanelSwitch(`from=${prev} to=${kind}`);
      return kind;
    });
  }, []);

  const onSelectTask = useCallback(
    (taskId: string) => {
      storeSelect(taskId);
    },
    [storeSelect],
  );

  const onClear = useCallback(() => {
    storeSelect(null);
  }, [storeSelect]);

  const onCenter = useCallback(() => {
    onRevealSelection?.();
    getTimelineInspectorMetrics().recordReveal();
  }, [onRevealSelection]);

  const onFocus = useCallback(() => {
    onFitSelection?.();
    getTimelineInspectorMetrics().recordFit();
  }, [onFitSelection]);

  return (
    <TaskInspector
      className={className}
      inspection={inspection}
      events={events}
      activePanel={activePanel}
      onSelectPanel={onSelectPanel}
      onSelectTask={onSelectTask}
      onClear={onClear}
      onCenter={onCenter}
      onFocus={onFocus}
    />
  );
}
