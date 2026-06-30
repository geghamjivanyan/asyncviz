/**
 * Public API for the semaphore contention visualization layer.
 *
 * Kept narrow on purpose — panel + container + diagnostics are the
 * supported integration surface. Internal types are re-exported so
 * tests + future custom containers can stay decoupled.
 */

export { SemaphoreContentionCard } from "@/dashboard/semaphores/SemaphoreContentionCard";
export { SemaphoreContentionContainer } from "@/dashboard/semaphores/SemaphoreContentionContainer";
export { SemaphoreContentionDiagnostics } from "@/dashboard/semaphores/SemaphoreContentionDiagnostics";
export { SemaphoreContentionOverlay } from "@/dashboard/semaphores/SemaphoreContentionOverlay";
export { SemaphoreContentionPanel } from "@/dashboard/semaphores/SemaphoreContentionPanel";
export { SemaphoreContentionTimeline } from "@/dashboard/semaphores/SemaphoreContentionTimeline";

export {
  projectSemaphoreContention,
  projectRecord,
  projectMarkersInWindow,
  describeMarker,
} from "@/dashboard/semaphores/SemaphoreContentionProjection";

export {
  layoutMarker,
  layoutMarkers,
  pickMarkerAt,
} from "@/dashboard/semaphores/SemaphoreContentionGeometry";

export {
  virtualizeList,
  virtualizeMarkers,
} from "@/dashboard/semaphores/SemaphoreContentionVirtualization";

export {
  hitTestMarkers,
  neighborSemaphoreId,
} from "@/dashboard/semaphores/SemaphoreContentionHitTesting";

export { layoutFrame, markerLayoutKey } from "@/dashboard/semaphores/SemaphoreContentionRenderer";

export {
  resetForReplay,
  replayEventPayload,
  replayEventStream,
} from "@/dashboard/semaphores/SemaphoreContentionReplay";

export {
  CRITICAL_UTILIZATION_THRESHOLD,
  CRITICAL_WAITER_THRESHOLD,
  SEVERITY_RANK,
  WARNING_UTILIZATION_THRESHOLD,
  compareSeverityDesc,
  deriveSeverity,
  markerLabel,
  severityLabel,
  utilizationOf,
} from "@/dashboard/semaphores/SemaphoreContentionSeverity";

export {
  describeMarkerAnnouncement,
  describeSemaphoreCountsAnnouncement,
  describeSemaphoreFocusAnnouncement,
  describeSemaphoreForAccessibility,
} from "@/dashboard/semaphores/SemaphoreContentionAccessibility";

export {
  DEFAULT_MARKER_CAPACITY,
  appendMarker,
  markerFromPayload,
  recordFromIdentity,
  reduceEventPayload,
  reduceHydration,
  useSemaphoreContentionStore,
} from "@/dashboard/semaphores/SemaphoreContentionStore";
export type {
  SemaphoreContentionStoreState,
  SemaphoreContentionStoreStats,
  SemaphoreContentionStoreStatus,
} from "@/dashboard/semaphores/SemaphoreContentionStore";

export {
  useSemaphoreRecords,
  useSemaphoreContentionViews,
  useSemaphoreContentionViewsBySeverity,
  useSelectedSemaphoreView,
  useSemaphoreContentionSelfMetrics,
  useSemaphoreContentionMarkers,
  useSemaphoreContentionStats,
  useSemaphoreContentionStatus,
  useSemaphoreContentionErrorMessage,
} from "@/dashboard/semaphores/selectors/SemaphoreContentionSelectors";

export { useSemaphoreContentionHydration } from "@/dashboard/semaphores/hooks/useSemaphoreContentionHydration";
export { useSemaphoreContentionWebsocketBridge } from "@/dashboard/semaphores/hooks/useSemaphoreContentionWebsocketBridge";
export { useSemaphoreContentionSelection } from "@/dashboard/semaphores/hooks/useSemaphoreContentionSelection";
export { useSemaphoreContentionViewsBundle } from "@/dashboard/semaphores/hooks/useSemaphoreContentionViews";

export {
  getSemaphoreContentionPanelMetrics,
  resetSemaphoreContentionPanelMetrics,
} from "@/dashboard/semaphores/diagnostics/SemaphoreContentionMetricsCollector";
export type { SemaphoreContentionPanelMetricsSnapshot } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionMetricsCollector";

export {
  clearSemaphoreContentionTrace,
  getSemaphoreContentionTrace,
  isSemaphoreContentionTraceEnabled,
  recordSemaphoreContentionTrace,
  setSemaphoreContentionTraceEnabled,
} from "@/dashboard/semaphores/diagnostics/SemaphoreContentionTracing";
export type {
  SemaphoreContentionTraceEntry,
  SemaphoreContentionTraceKind,
} from "@/dashboard/semaphores/diagnostics/SemaphoreContentionTracing";

export type {
  SemaphoreAcquireStartedPayload,
  SemaphoreAcquiredPayload,
  SemaphoreContentionDetectedPayload,
  SemaphoreContentionMarker,
  SemaphoreContentionSeverity,
  SemaphoreContentionView,
  SemaphoreCreatedPayload,
  SemaphoreEventPayload,
  SemaphoreEventType,
  SemaphoreHydrationResponse,
  SemaphoreIdentityRecord,
  SemaphoreKind,
  SemaphoreMarkerKind,
  SemaphoreMetricsRecord,
  SemaphoreRecord,
  SemaphoreReleasedPayload,
  SemaphoreSnapshotRecord,
  SemaphoreWaitCancelledPayload,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";
export { SEMAPHORE_EVENT_TYPES } from "@/dashboard/semaphores/models/SemaphoreContentionModels";
