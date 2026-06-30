/**
 * Event-rate card.
 *
 * Renders the rolling envelopes-per-second + the cumulative envelope
 * count. Stale / duplicate counters surface in the detail so that an
 * uptick is glanceable.
 */

import { memo } from "react";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
import { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
import { formatCount, formatRate } from "@/dashboard/metrics/utils/format";
import type { Intent } from "@/ui/theme/tokens";
import type { EventRateSummary } from "@/dashboard/metrics/models/summary";

export interface EventRateCardProps {
  eventRate: EventRateSummary;
}

function EventRateCardImpl({ eventRate }: EventRateCardProps) {
  const intent: Intent =
    eventRate.protocolErrors > 0 ? "danger" : eventRate.staleDropped > 0 ? "warning" : "default";
  const detail = `Applied ${formatCount(eventRate.envelopesApplied)} · Stale ${formatCount(
    eventRate.staleDropped,
  )} · Duplicate ${formatCount(eventRate.duplicatesDropped)}`;
  return (
    <MetricsCard
      id="event-rate"
      label="Runtime events"
      intent={intent}
      value={formatRate(eventRate.envelopesPerSecond)}
      trailing={<MetricsBadge intent={intent}>events/sec</MetricsBadge>}
      detail={detail}
    />
  );
}

export const EventRateCard = memo(EventRateCardImpl);
