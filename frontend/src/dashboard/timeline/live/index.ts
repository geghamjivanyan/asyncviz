/**
 * Public surface of the live timeline update engine.
 */

export {
  TimelineLiveEngine,
  type TimelineLiveEngineOptions,
} from "@/dashboard/timeline/live/TimelineLiveEngine";

export {
  TimelineInvalidationTracker,
  type PushRegionArgs,
} from "@/dashboard/timeline/live/TimelineInvalidation";

export {
  invalidateRow as invalidateRowRegion,
  invalidateRows as invalidateRowRegions,
} from "@/dashboard/timeline/live/TimelineRowInvalidation";

export {
  invalidateSegment as invalidateSegmentRegion,
  invalidateSegments as invalidateSegmentRegions,
} from "@/dashboard/timeline/live/TimelineSegmentInvalidation";

export {
  invalidateViewport as invalidateViewportRegion,
  invalidateSelection as invalidateSelectionRegion,
  invalidateWarnings as invalidateWarningRegion,
} from "@/dashboard/timeline/live/TimelineViewportInvalidation";

export {
  batchIsActionable,
  batchIsActiveTickOnly,
  batchToRendererReason,
  coalesceRegions,
} from "@/dashboard/timeline/live/TimelineDirtyRegions";

export {
  TimelineUpdateBatcher,
  type BatchingOptions,
  type ScheduleStrategy,
  type FlushFn,
} from "@/dashboard/timeline/live/TimelineUpdateBatching";

export {
  TimelineFrameScheduler,
  type FrameRequestSink,
  type FrameSchedulerOptions,
} from "@/dashboard/timeline/live/TimelineFrameScheduler";

export {
  TimelineDeltaProcessor,
  type DeltaProcessOptions,
  type DeltaProcessResult,
} from "@/dashboard/timeline/live/TimelineDeltaProcessor";

export {
  TimelineReplayCoordinator,
  type ReplayCoordinatorOptions,
  type ReplayBatchResult,
} from "@/dashboard/timeline/live/TimelineReplayCoordinator";

export {
  TimelineAnimationClock,
  type AnimationClockOptions,
  type AnimationTickListener,
} from "@/dashboard/timeline/live/TimelineAnimationClock";

export {
  TimelineLiveMetrics,
  getTimelineLiveMetrics,
  resetTimelineLiveMetrics,
  type TimelineLiveMetricsSnapshot,
} from "@/dashboard/timeline/live/TimelineLiveMetrics";

export {
  getLiveDiagnosticsSnapshot,
  clearLiveTrace,
  getLiveTraceSnapshot,
  isLiveTraceEnabled,
  recordLiveTrace,
  setLiveTraceEnabled,
  type LiveDiagnosticsSnapshot,
  type LiveTraceEntry,
} from "@/dashboard/timeline/live/TimelineLiveDiagnostics";

export {
  traceActiveTick,
  traceEnvelope,
  traceFlush,
  traceFrameRequest,
  traceInvalidate,
  traceModeChange,
  traceReplay,
} from "@/dashboard/timeline/live/TimelineUpdateTracing";

export {
  bindLiveEngineToClient,
  type UpdateCoordinatorBinding,
  type UpdateCoordinatorOptions,
} from "@/dashboard/timeline/live/TimelineUpdateCoordinator";

export {
  EMPTY_INVALIDATION_BATCH,
  type DirtyRegion,
  type InvalidationBatch,
  type InvalidationReason,
  type TimelineLiveMode,
  type TimelineReplayPhase,
} from "@/dashboard/timeline/live/models/TimelineLiveModels";

export {
  useActiveSegmentCount,
  useLastAppliedSequence,
} from "@/dashboard/timeline/live/selectors/storeLiveSelectors";
export { useTimelineLiveEngine } from "@/dashboard/timeline/live/hooks/useTimelineLiveEngine";
