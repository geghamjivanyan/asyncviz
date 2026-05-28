/**
 * Public surface of the canonical Zustand runtime store.
 *
 * Consumers import from this barrel — keeps the import paths short
 * and decouples them from the package's internal file layout.
 */

export { useRuntimeStore } from "@/state/runtime/store";
export type { RuntimeStoreState } from "@/state/runtime/store";

export {
  useActiveTimelineSegments,
  useActiveWarnings,
  useConnectedClients,
  useConnectionPhase,
  useConnectionState,
  useEvents,
  useLastSequence,
  useMetricsAggregate,
  useMetricsDeltaCounts,
  useReconciliationStats,
  useReplayMeta,
  useRuntimeMeta,
  useRuntimeStatus,
  useSelectedTask,
  useSelectedTaskId,
  useServerUptimeSeconds,
  useTasksById,
  useTasksInState,
  useTimelineSegmentsForTask,
  useWarningSeverityCounts,
} from "@/state/runtime/selectors";

export { useHydrateRuntime } from "@/state/runtime/hydration";

export { bindClientToStore } from "@/state/runtime/subscriptions";
export type { BindClientOptions, ClientStoreBinding } from "@/state/runtime/subscriptions";

export {
  classifyEnvelope,
  isTaskLifecycleEvent,
  reduceHeartbeat,
  reduceMetricsDelta,
  reduceTaskEvent,
  reduceTimelineDelta,
  reduceWarningDelta,
  reindexTaskState,
} from "@/state/runtime/reducers";
export type { HeartbeatProjection, TaskReduceResult } from "@/state/runtime/reducers";

export {
  normalizeTasks,
  normalizeTimeline,
  normalizeWarnings,
} from "@/state/runtime/normalization";

export { decideStoreSequence, maxSequence } from "@/state/runtime/sequencing";
export type { StoreSequenceDecision } from "@/state/runtime/sequencing";

export { HydrationConflictError, RuntimeStoreError } from "@/state/runtime/exceptions";

export {
  clearTrace,
  getTraceSnapshot,
  isStoreTraceEnabled,
  recordTrace,
  setStoreTraceEnabled,
} from "@/state/runtime/diagnostics";

export { TASK_STATES, TERMINAL_TASK_STATES } from "@/state/runtime/models";
export type {
  ConnectionMeta,
  DiagnosticsTrace,
  NormalizedMetricsState,
  NormalizedTimelineState,
  NormalizedWarningState,
  QueueMeta,
  ReconciliationStats,
  ReplayMeta,
  RuntimeEventEntry,
  RuntimeMeta,
} from "@/state/runtime/models";
