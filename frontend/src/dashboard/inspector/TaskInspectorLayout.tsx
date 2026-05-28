/**
 * Inspector layout — composes the header, toolbar, panel area, and
 * accessibility live region. Stateless: receives the inspection +
 * panel + handlers from the container.
 */

import { memo, useEffect, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import {
  TaskInspectorHeader,
  type TaskInspectorHeaderProps,
} from "@/dashboard/inspector/TaskInspectorHeader";
import {
  TaskInspectorToolbar,
  type TaskInspectorToolbarProps,
} from "@/dashboard/inspector/TaskInspectorToolbar";
import { describeInspection } from "@/dashboard/inspector/TaskInspectorAccessibility";
import { getTimelineInspectorMetrics } from "@/dashboard/inspector/TaskInspectorMetricsCollector";
import { traceInspectorPanelRender } from "@/dashboard/inspector/TaskInspectorTracing";
import type {
  InspectorPanelKind,
  TaskInspection,
} from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorLayoutProps {
  inspection: TaskInspection;
  activePanel: InspectorPanelKind;
  panel: ReactNode;
  toolbarBadges?: TaskInspectorToolbarProps["badges"];
  onSelectPanel: TaskInspectorToolbarProps["onSelect"];
  onFocus?: TaskInspectorHeaderProps["onFocus"];
  onCenter?: TaskInspectorHeaderProps["onCenter"];
  onClear?: TaskInspectorHeaderProps["onClear"];
  className?: string;
}

function TaskInspectorLayoutImpl({
  inspection,
  activePanel,
  panel,
  toolbarBadges,
  onSelectPanel,
  onFocus,
  onCenter,
  onClear,
  className,
}: TaskInspectorLayoutProps) {
  useEffect(() => {
    if (inspection.task === null) return;
    getTimelineInspectorMetrics().recordPanelRender(activePanel);
    traceInspectorPanelRender(`panel=${activePanel} task=${inspection.task.task_id}`);
  }, [activePanel, inspection.task]);

  return (
    <div
      data-task-inspector="true"
      className={cn(
        "flex h-full min-h-0 flex-col overflow-hidden border-l border-line bg-panel",
        className,
      )}
    >
      <TaskInspectorHeader
        inspection={inspection}
        onFocus={onFocus}
        onCenter={onCenter}
        onClear={onClear}
      />
      <TaskInspectorToolbar
        activePanel={activePanel}
        onSelect={onSelectPanel}
        badges={toolbarBadges}
      />
      <div
        data-task-inspector-panel-area="true"
        className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto p-3"
      >
        {panel}
      </div>
      <p
        role="status"
        aria-live="polite"
        className="sr-only"
        data-task-inspector-announcement="true"
      >
        {describeInspection(inspection)}
      </p>
    </div>
  );
}

export const TaskInspectorLayout = memo(TaskInspectorLayoutImpl);
