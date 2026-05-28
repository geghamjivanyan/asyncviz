/**
 * Public surface for the canonical blocking-warnings dashboard module.
 *
 * Importers should reach for these named exports rather than the
 * deep file paths — keeps the module boundary stable as internal
 * components get split / renamed.
 */

export { BlockingWarningsPanel } from "@/dashboard/warnings/blocking/BlockingWarningsPanel";
export type {
  BlockingWarningsPanelProps,
  BlockingWarningsPanelStatus,
} from "@/dashboard/warnings/blocking/BlockingWarningsPanel";

export { BlockingWarningsContainer } from "@/dashboard/warnings/blocking/BlockingWarningsContainer";
export type {
  BlockingWarningsContainerProps,
} from "@/dashboard/warnings/blocking/BlockingWarningsContainer";

export { BlockingWarningsDiagnostics } from "@/dashboard/warnings/blocking/BlockingWarningsDiagnostics";

export {
  useBlockingWarningStore,
  reduceHydration,
  reduceEvent,
  countActiveBySeverity,
  BLOCKING_WARNING_EVENT_TYPES,
} from "@/dashboard/warnings/blocking/BlockingWarningStore";
export type {
  BlockingWarningStoreState,
  BlockingWarningStoreStats,
  EventAppliedKind,
  ReduceEventOutcome,
} from "@/dashboard/warnings/blocking/BlockingWarningStore";

export {
  useBlockingWarningHydration,
  blockingWarningSnapshotUrl,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningHydration";
export type {
  BlockingWarningHydrationOptions,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningHydration";

export {
  useBlockingWarningLiveUpdates,
  injectBlockingWarningEvent,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningLiveUpdates";
export type {
  BlockingWarningSubscribeFactory,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningLiveUpdates";

export {
  useBlockingWarningWebsocketBridge,
  makeBlockingWarningSubscribeFactory,
  blockingPayloadFromEnvelope,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningWebsocketBridge";
export type {
  BlockingWarningEnvelopeSource,
  UseBlockingWarningWebsocketBridgeOptions,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningWebsocketBridge";

export {
  useBlockingWarningSelection,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningSelection";
export {
  useBlockingWarningProjections,
  useBlockingWarningFilter,
  useSelectedBlockingWarning,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningViews";
export type {
  BlockingWarningProjections,
} from "@/dashboard/warnings/blocking/hooks/useBlockingWarningViews";

export {
  applyFilter,
  bucketViews,
  compareViews,
  filterFromMode,
  groupFromEventPayload,
  intentFor,
  projectGroup,
  summarize,
  BLOCKING_SEVERITIES,
  DEFAULT_FILTER,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";
export type {
  BlockingWarningBuckets,
  BlockingWarningCounts,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";

export * from "@/dashboard/warnings/blocking/models/BlockingWarningModels";

export {
  describeCountsAnnouncement,
  describeTransitionAnnouncement,
  describeViewForAccessibility,
} from "@/dashboard/warnings/blocking/BlockingWarningAccessibility";

export {
  DEFAULT_ACTIVE_VISIBLE_CAP,
  DEFAULT_RECENT_VISIBLE_CAP,
  clampViews,
} from "@/dashboard/warnings/blocking/BlockingWarningVirtualization";
export type { VirtualizationResult } from "@/dashboard/warnings/blocking/BlockingWarningVirtualization";

export {
  BlockingWarningOverlayMarker,
} from "@/dashboard/warnings/blocking/BlockingWarningOverlay";
export type {
  BlockingWarningOverlayMarkerProps,
} from "@/dashboard/warnings/blocking/BlockingWarningOverlay";

export {
  getBlockingWarningPanelMetrics,
  resetBlockingWarningPanelMetrics,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";
export type {
  BlockingWarningPanelMetricsSnapshot,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";

export {
  clearBlockingWarningTrace,
  getBlockingWarningTraceSnapshot,
  isBlockingWarningTraceEnabled,
  recordBlockingWarningTrace,
  setBlockingWarningTraceEnabled,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";
export type {
  BlockingWarningTraceEntry,
  BlockingWarningTraceKind,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";
