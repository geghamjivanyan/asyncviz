/**
 * Store-aware wrapper for the metrics header.
 *
 * The container is the only piece that reaches into the runtime
 * store + the rolling-rate tracker. Everything below it (cards,
 * grid, badges) is pure data → JSX.
 */

import { MetricsHeader } from "@/dashboard/metrics/components/MetricsHeader";
import { useMetricsHeaderSnapshot } from "@/dashboard/metrics/hooks/useMetricsHeaderSnapshot";

export interface MetricsHeaderContainerProps {
  className?: string;
}

export function MetricsHeaderContainer({ className }: MetricsHeaderContainerProps) {
  const snapshot = useMetricsHeaderSnapshot();
  return <MetricsHeader snapshot={snapshot} className={className} />;
}
