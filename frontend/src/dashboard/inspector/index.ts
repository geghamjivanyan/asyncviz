/**
 * Public surface of the canonical task detail inspector.
 */

export { TaskInspector, type TaskInspectorProps } from "@/dashboard/inspector/TaskInspector";
export {
  TaskInspectorContainer,
  type TaskInspectorContainerProps,
} from "@/dashboard/inspector/TaskInspectorContainer";
export {
  TaskInspectorLayout,
  type TaskInspectorLayoutProps,
} from "@/dashboard/inspector/TaskInspectorLayout";
export {
  TaskInspectorHeader,
  type TaskInspectorHeaderProps,
} from "@/dashboard/inspector/TaskInspectorHeader";
export {
  TaskInspectorOverview,
  type TaskInspectorOverviewProps,
} from "@/dashboard/inspector/TaskInspectorOverview";
export {
  TaskInspectorTimeline,
  type TaskInspectorTimelineProps,
} from "@/dashboard/inspector/TaskInspectorTimeline";
export {
  TaskInspectorMetrics,
  type TaskInspectorMetricsProps,
} from "@/dashboard/inspector/TaskInspectorMetrics";
export {
  TaskInspectorWarnings,
  type TaskInspectorWarningsProps,
} from "@/dashboard/inspector/TaskInspectorWarnings";
export {
  TaskInspectorRelationships,
  type TaskInspectorRelationshipsProps,
} from "@/dashboard/inspector/TaskInspectorRelationships";
export {
  TaskInspectorEvents,
  type TaskInspectorEventsProps,
} from "@/dashboard/inspector/TaskInspectorEvents";
export {
  TaskInspectorReplay,
  type TaskInspectorReplayProps,
} from "@/dashboard/inspector/TaskInspectorReplay";
export {
  TaskInspectorLifecycle,
  type TaskInspectorLifecycleProps,
} from "@/dashboard/inspector/TaskInspectorLifecycle";
export {
  TaskInspectorMetadata,
  type TaskInspectorMetadataProps,
} from "@/dashboard/inspector/TaskInspectorMetadata";
export { TaskInspectorEmptyState } from "@/dashboard/inspector/TaskInspectorEmptyState";
export { TaskInspectorLoading } from "@/dashboard/inspector/TaskInspectorLoading";
export {
  TaskInspectorToolbar,
  type TaskInspectorToolbarProps,
} from "@/dashboard/inspector/TaskInspectorToolbar";
export { TaskInspectorDiagnosticsPanel } from "@/dashboard/inspector/TaskInspectorDiagnostics";

export {
  describeInspection,
  describePanelSwitch,
} from "@/dashboard/inspector/TaskInspectorAccessibility";

export {
  TaskInspectorMetrics as TaskInspectorMetricsCollector,
  getTimelineInspectorMetrics,
  resetTimelineInspectorMetrics,
  type TaskInspectorMetricsSnapshot,
} from "@/dashboard/inspector/TaskInspectorMetricsCollector";

export {
  clearInspectorTrace,
  getInspectorTraceSnapshot,
  isInspectorTraceEnabled,
  recordInspectorTrace,
  setInspectorTraceEnabled,
  traceInspectorEmptyState,
  traceInspectorFit,
  traceInspectorLoadingState,
  traceInspectorPanelRender,
  traceInspectorPanelSwitch,
  traceInspectorProjection,
  traceInspectorReveal,
  traceInspectorWarningCorrelation,
  type InspectorTraceEntry,
  type InspectorTraceKind,
} from "@/dashboard/inspector/TaskInspectorTracing";

export {
  buildLifecycleSummary,
  buildMetricsSummary,
  buildRelationships,
  buildReplaySummary,
  buildTaskInspection,
  buildTimelineSummary,
  buildWarningsSummary,
  type BuildInspectionArgs,
} from "@/dashboard/inspector/selectors/inspectionSelectors";

export {
  useReplayMetaSummary,
  useSelectedTaskActiveSegment,
  useSelectedTaskChildren,
  useSelectedTaskCoroutineThroughput,
  useSelectedTaskEvents,
  useSelectedTaskSegments,
  useSelectedTaskSiblingCount,
  useSelectedTaskSnapshot,
  useSelectedTaskTransitions,
  useSelectedTaskWarnings,
} from "@/dashboard/inspector/selectors/storeInspectionSelectors";

export { useTaskInspection } from "@/dashboard/inspector/hooks/useTaskInspection";
export {
  useInspectorFocusBridge,
  type InspectorFocusActions,
  type InspectorFocusBridge,
} from "@/dashboard/inspector/hooks/useInspectorFocusActions";

export {
  EMPTY_TASK_INSPECTION,
  INSPECTOR_PANEL_ORDER,
  type InspectorLifecycleState,
  type InspectorLifecycleSummary,
  type InspectorMetricsSummary,
  type InspectorPanelKind,
  type InspectorRelationships,
  type InspectorReplaySummary,
  type InspectorTimelineSummary,
  type InspectorWarningsSummary,
  type TaskInspection,
} from "@/dashboard/inspector/models/TaskInspectionModels";

export {
  formatDuration,
  formatLifecycleState,
  formatPercent,
  formatSequence,
  formatWallTime,
  severityIntent,
  shortenIdentifier,
} from "@/dashboard/inspector/utils/formatting";
