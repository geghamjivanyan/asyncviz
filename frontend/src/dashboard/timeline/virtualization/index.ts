/**
 * Public surface of the canonical timeline virtualization engine.
 */

export {
  TimelineVirtualizationEngine,
  type TimelineVirtualizationEngineOptions,
} from "@/dashboard/timeline/virtualization/TimelineVirtualizationEngine";

export {
  TimelineViewportWindow,
  type ViewportWindowOptions,
} from "@/dashboard/timeline/virtualization/TimelineViewportWindow";

export {
  TimelineSegmentWindowing,
  type SegmentWindowingOptions,
} from "@/dashboard/timeline/virtualization/TimelineSegmentWindowing";

export { projectRowWindow } from "@/dashboard/timeline/virtualization/TimelineRowWindowing";

export {
  cullRowsByWindow,
  cullSegmentsIndexed,
  cullSegmentsLinear,
  type CullableRow,
  type CullSegmentsIndexedArgs,
  type CullSegmentsLinearArgs,
} from "@/dashboard/timeline/virtualization/TimelineVisibilityCulling";

export {
  clampOverscan,
  resolveOverscan,
  type OverscanContext,
  type OverscanPolicyOptions,
} from "@/dashboard/timeline/virtualization/TimelineOverscan";

export {
  TimelineVirtualizationCache,
} from "@/dashboard/timeline/virtualization/TimelineVirtualizationCache";

export {
  TimelineWindowMetrics,
  getTimelineWindowMetrics,
  resetTimelineWindowMetrics,
  type TimelineWindowMetricsSnapshot,
} from "@/dashboard/timeline/virtualization/TimelineWindowMetrics";

export {
  invalidationSinkFromLiveEngine,
  type InvalidationSink,
  type InvalidationSubscription,
} from "@/dashboard/timeline/virtualization/TimelineWindowInvalidation";

export {
  projectionSignature,
  signatureEquals,
  type ReusableProjectionSignature,
} from "@/dashboard/timeline/virtualization/TimelineProjectionReuse";

export {
  bindVirtualizationToLiveEngine,
  type VirtualizationCoordinatorBinding,
} from "@/dashboard/timeline/virtualization/TimelineVirtualizationCoordinator";

export {
  getVirtualizationDiagnosticsSnapshot,
  clearVirtualizationTrace,
  getVirtualizationTraceSnapshot,
  isVirtualizationTraceEnabled,
  recordVirtualizationTrace,
  setVirtualizationTraceEnabled,
  type VirtualizationDiagnosticsSnapshot,
  type VirtualizationTraceEntry,
} from "@/dashboard/timeline/virtualization/TimelineVirtualizationDiagnostics";

export {
  traceCacheHit,
  traceCacheMiss,
  traceIndexBuild,
  traceRowCull,
  traceSegmentCull,
  traceVirtualizationInvalidate,
  traceWindowResolve,
} from "@/dashboard/timeline/virtualization/TimelineVirtualizationTracing";

export {
  TimelineSegmentSpatialIndex,
  type SpatialIndexable,
  type SpatialIndexOptions,
} from "@/dashboard/timeline/virtualization/utils/spatialIndex";

export {
  DEFAULT_OVERSCAN,
  type OverscanConfig,
  type TimelineRowWindow,
  type TimelineTimeWindow,
  type TimelineViewportWindowSnapshot,
  type VirtualizationFrame,
  type VirtualizationInputs,
} from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";

export {
  useSegmentCount,
  useTaskCount,
} from "@/dashboard/timeline/virtualization/selectors/storeVirtualizationSelectors";
export { useTimelineVirtualization } from "@/dashboard/timeline/virtualization/hooks/useTimelineVirtualization";
