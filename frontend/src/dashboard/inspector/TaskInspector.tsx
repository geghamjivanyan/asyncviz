/**
 * Canonical task detail inspector — composes the layout + the active
 * panel based on the supplied inspection. Stateless: container hooks
 * pass in the inspection + panel handlers.
 */

import { memo, useEffect, useMemo } from "react";
import { cn } from "@/lib/cn";
import {
  TaskInspectorLayout,
  type TaskInspectorLayoutProps,
} from "@/dashboard/inspector/TaskInspectorLayout";
import { TaskInspectorOverview } from "@/dashboard/inspector/TaskInspectorOverview";
import { TaskInspectorTimeline } from "@/dashboard/inspector/TaskInspectorTimeline";
import { TaskInspectorMetrics } from "@/dashboard/inspector/TaskInspectorMetrics";
import { TaskInspectorWarnings } from "@/dashboard/inspector/TaskInspectorWarnings";
import { TaskInspectorRelationships } from "@/dashboard/inspector/TaskInspectorRelationships";
import { TaskInspectorEvents } from "@/dashboard/inspector/TaskInspectorEvents";
import { TaskInspectorReplay } from "@/dashboard/inspector/TaskInspectorReplay";
import { TaskInspectorLifecycle } from "@/dashboard/inspector/TaskInspectorLifecycle";
import { TaskInspectorMetadata } from "@/dashboard/inspector/TaskInspectorMetadata";
import { TaskInspectorDiagnosticsPanel } from "@/dashboard/inspector/TaskInspectorDiagnostics";
import { TaskInspectorEmptyState } from "@/dashboard/inspector/TaskInspectorEmptyState";
import { TaskInspectorLoading } from "@/dashboard/inspector/TaskInspectorLoading";
import { getTimelineInspectorMetrics } from "@/dashboard/inspector/TaskInspectorMetricsCollector";
import {
  traceInspectorEmptyState,
  traceInspectorLoadingState,
} from "@/dashboard/inspector/TaskInspectorTracing";
import type {
  InspectorPanelKind,
  TaskInspection,
} from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorProps {
  inspection: TaskInspection;
  activePanel: InspectorPanelKind;
  loading?: boolean;
  events?: ReadonlyArray<{
    event_id: string;
    event_type: string;
    monotonic_ns: number;
    task_id: string;
  }>;
  onSelectPanel: (kind: InspectorPanelKind) => void;
  onSelectTask?: (taskId: string) => void;
  onFocus?: TaskInspectorLayoutProps["onFocus"];
  onCenter?: TaskInspectorLayoutProps["onCenter"];
  onClear?: TaskInspectorLayoutProps["onClear"];
  className?: string;
}

function TaskInspectorImpl({
  inspection,
  activePanel,
  loading,
  events,
  onSelectPanel,
  onSelectTask,
  onFocus,
  onCenter,
  onClear,
  className,
}: TaskInspectorProps) {
  const isEmpty = inspection.task === null;
  const isLoading = Boolean(loading);

  useEffect(() => {
    if (isLoading) {
      getTimelineInspectorMetrics().recordLoadingState();
      traceInspectorLoadingState(`generation=${inspection.generation}`);
    } else if (isEmpty) {
      getTimelineInspectorMetrics().recordEmptyState();
      traceInspectorEmptyState(`generation=${inspection.generation}`);
    } else {
      getTimelineInspectorMetrics().recordSelectionRebuild();
    }
  }, [isEmpty, isLoading, inspection.generation]);

  const panel = useMemo(() => {
    if (isLoading) return <TaskInspectorLoading />;
    if (isEmpty) return <TaskInspectorEmptyState />;
    switch (activePanel) {
      case "overview":
        return <TaskInspectorOverview inspection={inspection} />;
      case "timeline":
        return <TaskInspectorTimeline inspection={inspection} />;
      case "metrics":
        return <TaskInspectorMetrics inspection={inspection} />;
      case "warnings":
        return <TaskInspectorWarnings inspection={inspection} />;
      case "relationships":
        return <TaskInspectorRelationships inspection={inspection} onSelectTask={onSelectTask} />;
      case "events":
        return <TaskInspectorEvents events={events ?? []} />;
      case "replay":
        return <TaskInspectorReplay inspection={inspection} />;
      case "lifecycle":
        return <TaskInspectorLifecycle inspection={inspection} />;
      case "metadata":
        return <TaskInspectorMetadata inspection={inspection} />;
      case "diagnostics":
        return <TaskInspectorDiagnosticsPanel />;
      default:
        return <TaskInspectorOverview inspection={inspection} />;
    }
  }, [activePanel, events, inspection, isEmpty, isLoading, onSelectTask]);

  const toolbarBadges = useMemo(
    () => ({
      warnings: inspection.warnings.count,
      events: events?.length ?? 0,
    }),
    [inspection.warnings.count, events?.length],
  );

  return (
    <TaskInspectorLayout
      inspection={inspection}
      activePanel={activePanel}
      panel={<div className={cn(className)}>{panel}</div>}
      toolbarBadges={toolbarBadges}
      onSelectPanel={onSelectPanel}
      onFocus={isEmpty ? undefined : onFocus}
      onCenter={isEmpty ? undefined : onCenter}
      onClear={isEmpty ? undefined : onClear}
    />
  );
}

export const TaskInspector = memo(TaskInspectorImpl);
