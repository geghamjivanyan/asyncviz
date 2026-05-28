/**
 * Public surface of the metrics-header system.
 *
 * Consumers import from this barrel — the internal layout (components,
 * hooks, selectors, observability, utils) can evolve without breaking
 * callers.
 */

export { MetricsHeader } from "@/dashboard/metrics/components/MetricsHeader";
export type { MetricsHeaderProps } from "@/dashboard/metrics/components/MetricsHeader";
export { MetricsHeaderContainer } from "@/dashboard/metrics/components/MetricsHeaderContainer";
export type { MetricsHeaderContainerProps } from "@/dashboard/metrics/components/MetricsHeaderContainer";
export { MetricsGrid } from "@/dashboard/metrics/components/MetricsGrid";
export { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
export type { MetricsCardProps } from "@/dashboard/metrics/components/MetricsCard";
export { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
export type { MetricsBadgeProps } from "@/dashboard/metrics/components/MetricsBadge";
export { MetricsStatus } from "@/dashboard/metrics/components/MetricsStatus";
export type { MetricsStatusProps } from "@/dashboard/metrics/components/MetricsStatus";
export { MetricsSparkline } from "@/dashboard/metrics/components/MetricsSparkline";
export type { MetricsSparklineProps } from "@/dashboard/metrics/components/MetricsSparkline";
export { MetricsSummary } from "@/dashboard/metrics/components/MetricsSummary";
export type { MetricsSummaryProps } from "@/dashboard/metrics/components/MetricsSummary";
export { MetricsDiagnostics } from "@/dashboard/metrics/components/MetricsDiagnostics";

export { RuntimeHealthCard } from "@/dashboard/metrics/components/RuntimeHealthCard";
export { ConnectionStatusCard } from "@/dashboard/metrics/components/ConnectionStatusCard";
export { ReplayStatusCard } from "@/dashboard/metrics/components/ReplayStatusCard";
export { WarningSummaryCard } from "@/dashboard/metrics/components/WarningSummaryCard";
export { ThroughputCard } from "@/dashboard/metrics/components/ThroughputCard";
export { EventRateCard } from "@/dashboard/metrics/components/EventRateCard";
export { RuntimeClockCard } from "@/dashboard/metrics/components/RuntimeClockCard";
export { TaskCountsCard } from "@/dashboard/metrics/components/TaskCountsCard";

export type {
  ConnectionSummary,
  EventRateSummary,
  MetricsHeaderSnapshot,
  ReplaySummary,
  RuntimeClockSummary,
  RuntimeHealthLevel,
  RuntimeHealthSummary,
  TaskCountSummary,
  ThroughputSummary,
  WarningSummary,
} from "@/dashboard/metrics/models/summary";
export {
  WARNING_SEVERITY_RANK,
  emptySeverityCounts,
  highestSeverity,
  totalWarningCount,
} from "@/dashboard/metrics/models/summary";

export {
  createRateTracker,
  rateFromTracker,
  recordRateSample,
  type RateSample,
  type RateTrackerState,
} from "@/dashboard/metrics/models/rateTracker";

export {
  projectClock,
  projectConnection,
  projectEventRate,
  projectHealth,
  projectMetricsHeader,
  projectReplay,
  projectTaskCounts,
  projectThroughput,
  projectWarnings,
  type ProjectionInputs,
} from "@/dashboard/metrics/selectors/projectSummaries";

export { useMetricsHeaderSnapshot } from "@/dashboard/metrics/hooks/useMetricsHeaderSnapshot";
export { useEnvelopesPerSecond } from "@/dashboard/metrics/hooks/useEnvelopesPerSecond";
export { useNowMs } from "@/dashboard/metrics/hooks/useNowMs";

export {
  formatCount,
  formatLagMs,
  formatPercent,
  formatRate,
  formatSequence,
  formatUptime,
} from "@/dashboard/metrics/utils/format";

export {
  MetricsHeaderMetrics,
  type MetricsHeaderMetricsSnapshot,
  getMetricsHeaderMetrics,
  resetMetricsHeaderMetrics,
} from "@/dashboard/metrics/observability";
