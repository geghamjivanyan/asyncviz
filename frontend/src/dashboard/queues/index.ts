/**
 * Public API for the queue pressure visualization layer.
 *
 * Kept narrow on purpose — the panel + diagnostics components are the
 * supported integration surface. Geometry / projection / store types
 * are re-exported for tests + future custom containers (replay
 * scrubber, distributed-runtime aggregator).
 */

export { QueuePressureCard } from "@/dashboard/queues/QueuePressureCard";
export { QueuePressureContainer } from "@/dashboard/queues/QueuePressureContainer";
export { QueuePressureDiagnostics } from "@/dashboard/queues/QueuePressureDiagnostics";
export { QueuePressureOverlay } from "@/dashboard/queues/QueuePressureOverlay";
export { QueuePressurePanel } from "@/dashboard/queues/QueuePressurePanel";
export { QueuePressureTimeline } from "@/dashboard/queues/QueuePressureTimeline";

export {
  projectQueuePressure,
  projectRecord,
  projectMarkersInWindow,
  describeMarker,
} from "@/dashboard/queues/QueuePressureProjection";

export {
  layoutMarker,
  layoutMarkers,
  pickMarkerAt,
} from "@/dashboard/queues/QueuePressureGeometry";

export { virtualizeList, virtualizeMarkers } from "@/dashboard/queues/QueuePressureVirtualization";

export { hitTestMarkers, neighborQueueId } from "@/dashboard/queues/QueuePressureHitTesting";

export { layoutFrame, markerLayoutKey } from "@/dashboard/queues/QueuePressureRenderer";

export {
  resetForReplay,
  replayEventPayload,
  replayEventStream,
} from "@/dashboard/queues/QueuePressureReplay";

export {
  deriveSeverity,
  compareSeverityDesc,
  severityLabel,
  markerLabel,
  SEVERITY_RANK,
} from "@/dashboard/queues/QueuePressureSeverity";

export {
  describeMarkerAnnouncement,
  describeQueueCountsAnnouncement,
  describeQueueFocusAnnouncement,
  describeQueueForAccessibility,
} from "@/dashboard/queues/QueuePressureAccessibility";

export {
  useQueuePressureStore,
  reduceEventPayload,
  reduceHydration,
  appendMarker,
  markerFromPayload,
  DEFAULT_MARKER_CAPACITY,
} from "@/dashboard/queues/QueuePressureStore";
export type {
  QueuePressureStoreState,
  QueuePressureStoreStats,
  QueuePressureStoreStatus,
} from "@/dashboard/queues/QueuePressureStore";

export {
  useQueueRecords,
  useQueuePressureViews,
  useQueuePressureViewsBySeverity,
  useSelectedQueueView,
  useQueuePressureSelfMetrics,
  useQueuePressureMarkers,
  useQueuePressureStats,
  useQueuePressureStatus,
  useQueuePressureErrorMessage,
} from "@/dashboard/queues/selectors/QueuePressureSelectors";

export { useQueuePressureHydration } from "@/dashboard/queues/hooks/useQueuePressureHydration";
export { useQueuePressureWebsocketBridge } from "@/dashboard/queues/hooks/useQueuePressureWebsocketBridge";
export { useQueuePressureSelection } from "@/dashboard/queues/hooks/useQueuePressureSelection";
export { useQueuePressureViewsBundle } from "@/dashboard/queues/hooks/useQueuePressureViews";

export {
  getQueuePressurePanelMetrics,
  resetQueuePressurePanelMetrics,
} from "@/dashboard/queues/diagnostics/QueuePressureMetricsCollector";
export type { QueuePressurePanelMetricsSnapshot } from "@/dashboard/queues/diagnostics/QueuePressureMetricsCollector";

export {
  clearQueuePressureTrace,
  getQueuePressureTrace,
  isQueuePressureTraceEnabled,
  recordQueuePressureTrace,
  setQueuePressureTraceEnabled,
} from "@/dashboard/queues/diagnostics/QueuePressureTracing";
export type {
  QueuePressureTraceEntry,
  QueuePressureTraceKind,
} from "@/dashboard/queues/diagnostics/QueuePressureTracing";

export type {
  QueueContentionKind,
  QueueContentionRecord,
  QueueMetricsEngineSelfRecord,
  QueueMetricsEventPayload,
  QueueMetricsEventType,
  QueueMetricsHydrationResponse,
  QueueMetricsRecord,
  QueueMetricsSnapshot,
  QueueOccupancyRecord,
  QueuePressureLevel,
  QueuePressureMarker,
  QueuePressureMarkerKind,
  QueuePressureRecord,
  QueuePressureSeverity,
  QueuePressureView,
  QueueThroughputRecord,
  QueueWaitRecord,
} from "@/dashboard/queues/models/QueuePressureModels";
export { QUEUE_METRICS_EVENT_TYPES } from "@/dashboard/queues/models/QueuePressureModels";
