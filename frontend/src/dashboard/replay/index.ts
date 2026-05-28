/**
 * Public API for the replay timeline controls.
 */

export { ReplayPlaybackControls } from "@/dashboard/replay/ReplayPlaybackControls";
export { REPLAY_SPEED_PRESETS } from "@/dashboard/replay/ReplayPlaybackPresets";
export { ReplayTimelineBookmarks } from "@/dashboard/replay/ReplayTimelineBookmarks";
export { ReplayTimelineControls } from "@/dashboard/replay/ReplayTimelineControls";
export { ReplayTimelineMarkers } from "@/dashboard/replay/ReplayTimelineMarkers";
export { ReplayTimelineMiniMap } from "@/dashboard/replay/ReplayTimelineMiniMap";
export { ReplayTimelinePlayback } from "@/dashboard/replay/ReplayTimelinePlayback";
export { ReplayTimelineScrubber } from "@/dashboard/replay/ReplayTimelineScrubber";
export { ReplayTimelineSelection } from "@/dashboard/replay/ReplayTimelineSelection";

export type {
  ReplayBookmark,
  ReplayControlIntent,
  ReplayMarkerKind,
  ReplayMarkerSeverity,
  ReplayPlaybackSnapshot,
  ReplayPlaybackState,
  ReplayScrubPhase,
  ReplayScrubPreview,
  ReplaySessionWindow,
  ReplayTimelineBucket,
  ReplayTimelineMarker,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export {
  clamp,
  fractionToSequence,
  pixelToSequence,
  sequenceInViewport,
  sequenceToFraction,
  sequenceToPixel,
  sequenceToTimestamp,
  timestampToSequence,
  viewportForWindow,
} from "@/dashboard/replay/ReplayTimelineGeometry";

export {
  bucketMarkers,
  findNearestMarker,
  projectBookmarks,
  projectMarkers,
} from "@/dashboard/replay/ReplayTimelineProjection";
export type {
  ReplayBookmarkPlacement,
  ReplayMarkerPlacement,
} from "@/dashboard/replay/ReplayTimelineProjection";

export {
  jumpByFraction,
  seekFromFraction,
  seekFromPixel,
  seekToBookmark,
  seekToMarker,
  seekToTimestampForSequence,
  stepCursor,
} from "@/dashboard/replay/ReplayTimelineSeek";

export {
  pickClusterAt,
  virtualizeMarkers,
  type ReplayMarkerCluster,
} from "@/dashboard/replay/ReplayTimelineVirtualization";

export {
  announceSeekCompleted,
  announceStateTransition,
  describeBookmarkForAccessibility,
  describeMarkerForAccessibility,
  describePlaybackForAccessibility,
  REPLAY_KEYBOARD_HELP,
} from "@/dashboard/replay/ReplayTimelineAccessibility";

export {
  initialReplayTimelineState,
  reduceAddBookmark,
  reduceAppendMarker,
  reduceBeginScrub,
  reduceEndScrub,
  reducePlayback,
  reduceRemoveBookmark,
  reduceUpdateScrub,
  useReplayTimelineStore,
  type ReplayTimelineStats,
  type ReplayTimelineStoreState,
} from "@/dashboard/replay/ReplayTimelineStore";

export {
  useReplayBookmarks,
  useReplayFocusedBookmarkId,
  useReplayFocusedMarkerId,
  useReplayMarkers,
  useReplayPlayback,
  useReplayScrubPhase,
  useReplayScrubPreview,
  useReplayTimelineStats,
  useReplayViewport,
  useReplayWindow,
} from "@/dashboard/replay/ReplayTimelineSelectors";

export {
  InMemoryReplayEngineBridge,
  type ReplayEngineBridge,
  type ReplayEngineUnsubscribe,
} from "@/dashboard/replay/hooks/ReplayEngineBridge";
export { useReplayEngineBridge } from "@/dashboard/replay/hooks/useReplayEngineBridge";
export { useReplayKeyboard, mapKeyToIntent } from "@/dashboard/replay/hooks/useReplayKeyboard";
export { useReplayScrub } from "@/dashboard/replay/hooks/useReplayScrub";

export {
  getReplayTimelineMetricsSnapshot,
  recordBookmarkAdded,
  recordBookmarkRemoved,
  recordBucketRenderPass,
  recordFocusChange,
  recordKeyboardEvent,
  recordMarkerRenderPass,
  recordScrubEnd,
  recordScrubStart,
  recordScrubUpdate,
  recordSeekChange,
  recordSeekRequested,
  resetReplayTimelineMetrics,
  type ReplayTimelineMetricsSnapshot,
} from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";

export {
  clearReplayTimelineTrace,
  getReplayTimelineTrace,
  isReplayTimelineTraceEnabled,
  recordReplayTimelineTrace,
  setReplayTimelineTraceEnabled,
  type ReplayTimelineTraceEntry,
  type ReplayTimelineTraceKind,
} from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";

export {
  buildReplayTimelineDiagnostics,
  type ReplayTimelineDiagnostics,
} from "@/dashboard/replay/diagnostics/ReplayTimelineDiagnostics";
