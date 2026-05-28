/**
 * Public surface of the connection-status system.
 *
 * Consumers import from this barrel — internal layout can evolve
 * without breaking callers.
 */

export { ConnectionStatusIndicator } from "@/dashboard/connection/components/ConnectionStatusIndicator";
export type { ConnectionStatusIndicatorProps } from "@/dashboard/connection/components/ConnectionStatusIndicator";
export { ConnectionStatusContainer } from "@/dashboard/connection/components/ConnectionStatusContainer";
export type { ConnectionStatusContainerProps } from "@/dashboard/connection/components/ConnectionStatusContainer";
export { ConnectionStatusBadge } from "@/dashboard/connection/components/ConnectionStatusBadge";
export type { ConnectionStatusBadgeProps } from "@/dashboard/connection/components/ConnectionStatusBadge";
export { ConnectionPhaseIndicator } from "@/dashboard/connection/components/ConnectionPhaseIndicator";
export { ReplaySyncIndicator } from "@/dashboard/connection/components/ReplaySyncIndicator";
export { HydrationIndicator } from "@/dashboard/connection/components/HydrationIndicator";
export { HeartbeatIndicator } from "@/dashboard/connection/components/HeartbeatIndicator";
export { ConnectionTooltip } from "@/dashboard/connection/components/ConnectionTooltip";
export type { ConnectionTooltipProps } from "@/dashboard/connection/components/ConnectionTooltip";
export { ConnectionHistory } from "@/dashboard/connection/components/ConnectionHistory";
export type { ConnectionHistoryProps } from "@/dashboard/connection/components/ConnectionHistory";
export { ConnectionTimeline } from "@/dashboard/connection/components/ConnectionTimeline";
export type { ConnectionTimelineProps } from "@/dashboard/connection/components/ConnectionTimeline";
export { ConnectionToolbar } from "@/dashboard/connection/components/ConnectionToolbar";
export type { ConnectionToolbarProps } from "@/dashboard/connection/components/ConnectionToolbar";
export { ConnectionDiagnostics } from "@/dashboard/connection/components/ConnectionDiagnostics";

export {
  FLAKY_RECONNECT_THRESHOLD,
  HEARTBEAT_OFFLINE_MS,
  HEARTBEAT_STALE_MS,
  HISTORY_RING_CAPACITY,
  type ConnectionHistoryEntry,
  type ConnectionHistoryKind,
  type ConnectionPhaseSummary,
  type ConnectionSummary,
  type ConnectionVisibility,
  type HeartbeatSummary,
  type HydrationSummary,
  type ReconnectSummary,
  type ReplaySyncSummary,
} from "@/dashboard/connection/models/state";

export { appendHistory, clearHistory } from "@/dashboard/connection/models/history";

export {
  projectConnection,
  projectHeartbeat,
  projectHydration,
  projectPhase,
  projectReconnect,
  projectReplaySync,
  type ConnectionProjectionInputs,
} from "@/dashboard/connection/selectors/projectConnection";

export { useConnectionSummary } from "@/dashboard/connection/hooks/useConnectionSummary";
export { useConnectionHistory } from "@/dashboard/connection/hooks/useConnectionHistory";
export type { ConnectionHistory as ConnectionHistoryValue } from "@/dashboard/connection/hooks/useConnectionHistory";
export { useNowMs } from "@/dashboard/connection/hooks/useNowMs";

export {
  formatDurationMs,
  formatLagMs,
  formatPercent,
  formatSequence,
  formatWallTime,
} from "@/dashboard/connection/utils/format";

export {
  ConnectionMetrics,
  type ConnectionMetricsSnapshot,
  getConnectionMetrics,
  resetConnectionMetrics,
} from "@/dashboard/connection/observability";
