/**
 * Public API for the executor activity visualization layer.
 */

export { ExecutorActivityCard } from "@/dashboard/executors/ExecutorActivityCard";
export { ExecutorActivityContainer } from "@/dashboard/executors/ExecutorActivityContainer";
export { ExecutorActivityDiagnostics } from "@/dashboard/executors/ExecutorActivityDiagnostics";
export { ExecutorActivityOverlay } from "@/dashboard/executors/ExecutorActivityOverlay";
export { ExecutorActivityPanel } from "@/dashboard/executors/ExecutorActivityPanel";
export { ExecutorActivityTimeline } from "@/dashboard/executors/ExecutorActivityTimeline";

export {
  projectExecutorActivity,
  projectRecord,
  projectMarkersInWindow,
  describeMarker,
} from "@/dashboard/executors/ExecutorActivityProjection";

export {
  layoutMarker,
  layoutMarkers,
  pickMarkerAt,
} from "@/dashboard/executors/ExecutorActivityGeometry";

export {
  virtualizeList,
  virtualizeMarkers,
} from "@/dashboard/executors/ExecutorActivityVirtualization";

export {
  hitTestMarkers,
  neighborExecutorId,
} from "@/dashboard/executors/ExecutorActivityHitTesting";

export { layoutFrame, markerLayoutKey } from "@/dashboard/executors/ExecutorActivityRenderer";

export {
  replayEventPayload,
  replayEventStream,
  resetForReplay,
} from "@/dashboard/executors/ExecutorActivityReplay";

export {
  SEVERITY_RANK,
  compareSeverityDesc,
  deriveSeverity,
  markerLabel,
  severityLabel,
} from "@/dashboard/executors/ExecutorActivitySeverity";

export {
  describeExecutorCountsAnnouncement,
  describeExecutorFocusAnnouncement,
  describeExecutorForAccessibility,
  describeMarkerAnnouncement,
} from "@/dashboard/executors/ExecutorActivityAccessibility";

export {
  DEFAULT_MARKER_CAPACITY,
  appendMarker,
  markerFromPayload,
  reduceEventPayload,
  reduceHydration,
  useExecutorActivityStore,
} from "@/dashboard/executors/ExecutorActivityStore";
export type {
  ExecutorActivityStoreState,
  ExecutorActivityStoreStats,
  ExecutorActivityStoreStatus,
} from "@/dashboard/executors/ExecutorActivityStore";

export {
  useExecutorActivityErrorMessage,
  useExecutorActivityMarkers,
  useExecutorActivitySelfMetrics,
  useExecutorActivityStats,
  useExecutorActivityStatus,
  useExecutorActivityViews,
  useExecutorActivityViewsBySeverity,
  useExecutorRecords,
  useSelectedExecutorView,
} from "@/dashboard/executors/selectors/ExecutorActivitySelectors";

export { useExecutorActivityHydration } from "@/dashboard/executors/hooks/useExecutorActivityHydration";
export { useExecutorActivityWebsocketBridge } from "@/dashboard/executors/hooks/useExecutorActivityWebsocketBridge";
export { useExecutorActivitySelection } from "@/dashboard/executors/hooks/useExecutorActivitySelection";
export { useExecutorActivityViewsBundle } from "@/dashboard/executors/hooks/useExecutorActivityViews";

export {
  getExecutorActivityPanelMetrics,
  resetExecutorActivityPanelMetrics,
} from "@/dashboard/executors/diagnostics/ExecutorActivityMetricsCollector";
export type { ExecutorActivityPanelMetricsSnapshot } from "@/dashboard/executors/diagnostics/ExecutorActivityMetricsCollector";

export {
  clearExecutorActivityTrace,
  getExecutorActivityTrace,
  isExecutorActivityTraceEnabled,
  recordExecutorActivityTrace,
  setExecutorActivityTraceEnabled,
} from "@/dashboard/executors/diagnostics/ExecutorActivityTracing";
export type {
  ExecutorActivityTraceEntry,
  ExecutorActivityTraceKind,
} from "@/dashboard/executors/diagnostics/ExecutorActivityTracing";

export type {
  ExecutorActivityEventPayload,
  ExecutorActivityEventType,
  ExecutorActivityHydrationResponse,
  ExecutorActivityMarker,
  ExecutorActivitySeverity,
  ExecutorActivityView,
  ExecutorContentionDetectedPayload,
  ExecutorEngineSelfRecord,
  ExecutorKind,
  ExecutorLatencyRecord,
  ExecutorLatencySpikeDetectedPayload,
  ExecutorMarkerKind,
  ExecutorMetricsRecord,
  ExecutorMetricsUpdatedPayload,
  ExecutorSaturationChangedPayload,
  ExecutorSaturationLevel,
  ExecutorSaturationRecord,
  ExecutorThroughputRecord,
  ExecutorUtilizationRecord,
} from "@/dashboard/executors/models/ExecutorActivityModels";
export { EXECUTOR_METRICS_EVENT_TYPES } from "@/dashboard/executors/models/ExecutorActivityModels";
