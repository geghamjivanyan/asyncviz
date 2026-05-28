/**
 * Public API for the await dependency graph layer.
 */

export { AwaitDependencyCanvas } from "@/dashboard/dependencies/AwaitDependencyCanvas";
export { AwaitDependencyDiagnostics } from "@/dashboard/dependencies/AwaitDependencyDiagnostics";
export { AwaitDependencyGraph } from "@/dashboard/dependencies/AwaitDependencyGraph";
export { AwaitDependencyGraphContainer } from "@/dashboard/dependencies/AwaitDependencyGraphContainer";

export {
  projectDependencies,
  projectEdge,
  projectNode,
} from "@/dashboard/dependencies/AwaitDependencyProjection";
export type { AwaitDependencyProjection } from "@/dashboard/dependencies/AwaitDependencyProjection";

export {
  layoutDependencies,
} from "@/dashboard/dependencies/layout/AwaitDependencyLayout";
export type {
  LaidEdge,
  LaidNode,
  LayoutFrame,
  LayoutInputs,
} from "@/dashboard/dependencies/layout/AwaitDependencyLayout";

export {
  clipToViewport,
  edgeIntersectsViewport,
  intersectsViewport,
} from "@/dashboard/dependencies/AwaitDependencyGeometry";
export type { Viewport } from "@/dashboard/dependencies/AwaitDependencyGeometry";

export {
  virtualize,
} from "@/dashboard/dependencies/AwaitDependencyVirtualization";

export {
  nodeAt,
  neighborNodeId,
} from "@/dashboard/dependencies/AwaitDependencyHitTesting";

export {
  buildDependencyFrame,
} from "@/dashboard/dependencies/AwaitDependencyRenderer";
export type {
  DependencyFrame,
  DependencyFrameInputs,
} from "@/dashboard/dependencies/AwaitDependencyRenderer";

export {
  replayEventPayload,
  replayEventStream,
  resetForReplay,
} from "@/dashboard/dependencies/AwaitDependencyReplay";

export {
  compareSeverityDesc,
  edgeKindLabel,
  nodeKindLabel,
  severityForState,
  stateLabel,
} from "@/dashboard/dependencies/AwaitDependencySeverity";
export type { AwaitNodeSeverity } from "@/dashboard/dependencies/AwaitDependencySeverity";

export {
  describeEdgeForAccessibility,
  describeFocusAnnouncement,
  describeNodeForAccessibility,
  describeTopologyAnnouncement,
} from "@/dashboard/dependencies/AwaitDependencyAccessibility";

export {
  DEFAULT_MAX_NODES,
  reduceEventPayload,
  useAwaitDependencyStore,
} from "@/dashboard/dependencies/AwaitDependencyStore";
export type {
  AwaitDependencyStoreState,
  AwaitDependencyStoreStats,
  AwaitDependencyStoreStatus,
} from "@/dashboard/dependencies/AwaitDependencyStore";

export {
  useAwaitDependencyEdgeRecords,
  useAwaitDependencyErrorMessage,
  useAwaitDependencyNodeRecords,
  useAwaitDependencyStats,
  useAwaitDependencyStatus,
  useAwaitDependencyViews,
  useSelectedAwaitNodeView,
} from "@/dashboard/dependencies/selectors/AwaitDependencySelectors";

export { useAwaitDependencyWebsocketBridge } from "@/dashboard/dependencies/hooks/useAwaitDependencyWebsocketBridge";
export { useAwaitDependencySelection } from "@/dashboard/dependencies/hooks/useAwaitDependencySelection";

export {
  getAwaitDependencyPanelMetrics,
  resetAwaitDependencyPanelMetrics,
} from "@/dashboard/dependencies/diagnostics/AwaitDependencyMetricsCollector";
export type { AwaitDependencyMetricsSnapshot } from "@/dashboard/dependencies/diagnostics/AwaitDependencyMetricsCollector";

export {
  clearAwaitDependencyTrace,
  getAwaitDependencyTrace,
  isAwaitDependencyTraceEnabled,
  recordAwaitDependencyTrace,
  setAwaitDependencyTraceEnabled,
} from "@/dashboard/dependencies/diagnostics/AwaitDependencyTracing";
export type {
  AwaitDependencyTraceEntry,
  AwaitDependencyTraceKind,
} from "@/dashboard/dependencies/diagnostics/AwaitDependencyTracing";

export type {
  AwaitEdgeKind,
  AwaitEdgeRecord,
  AwaitEdgeView,
  AwaitGatherEventPayload,
  AwaitNodeKind,
  AwaitNodeRecord,
  AwaitNodeState,
  AwaitNodeView,
  GatherCancelledPayload,
  GatherChildAttachedPayload,
  GatherChildCompletedPayload,
  GatherCompletedPayload,
  GatherCreatedPayload,
  GatherEventType,
  GatherFailedPayload,
  GatherWaitStartedPayload,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";
export { GATHER_EVENT_TYPES } from "@/dashboard/dependencies/models/AwaitDependencyModels";
