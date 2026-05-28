/**
 * Runtime-health card.
 *
 * Renders the canonical health level as a colored badge with a verbal
 * label. Critical / error states promote the card border to the
 * matching intent so the row is visually scannable.
 */

import { memo } from "react";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
import { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
import type { Intent } from "@/ui/theme/tokens";
import type { RuntimeHealthSummary } from "@/dashboard/metrics/models/summary";

const INTENT_BY_LEVEL: Record<RuntimeHealthSummary["level"], Intent> = {
  healthy: "success",
  degraded: "warning",
  unavailable: "danger",
  starting: "accent",
  unknown: "default",
};

export interface RuntimeHealthCardProps {
  health: RuntimeHealthSummary;
}

function RuntimeHealthCardImpl({ health }: RuntimeHealthCardProps) {
  const intent = INTENT_BY_LEVEL[health.level];
  const detail = health.isPaused
    ? "Runtime paused"
    : health.hasCriticalWarning
      ? "Critical warnings"
      : health.isHydrating
        ? "Hydrating snapshot"
        : "Runtime nominal";
  return (
    <MetricsCard
      id="runtime-health"
      label="Health"
      intent={intent}
      value={health.label}
      trailing={
        <MetricsBadge
          intent={intent}
          pulse={health.level === "healthy"}
          ariaLabel={`Runtime health ${health.label}`}
        >
          {health.level}
        </MetricsBadge>
      }
      detail={detail}
    />
  );
}

export const RuntimeHealthCard = memo(RuntimeHealthCardImpl);
