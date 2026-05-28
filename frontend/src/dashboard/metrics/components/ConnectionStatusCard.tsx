/**
 * Connection-status card.
 *
 * Renders the websocket :type:`ConnectionPhase` as a labeled badge.
 * The pulse dot lights up only while the phase is ``live``.
 */

import { memo } from "react";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
import { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
import { formatLagMs, formatCount } from "@/dashboard/metrics/utils/format";
import type { Intent } from "@/ui/theme/tokens";
import type { ConnectionSummary } from "@/dashboard/metrics/models/summary";
import type { ConnectionPhase } from "@/runtime/websocket";

const PHASE_INTENT: Record<ConnectionPhase, Intent> = {
  idle: "default",
  hydrating: "accent",
  connecting: "warning",
  replaying: "accent",
  live: "success",
  reconnecting: "warning",
  disconnected: "default",
  failed: "danger",
};

export interface ConnectionStatusCardProps {
  connection: ConnectionSummary;
}

function ConnectionStatusCardImpl({ connection }: ConnectionStatusCardProps) {
  const intent = PHASE_INTENT[connection.phase];
  const detail = connection.isReconnecting
    ? `Retry ${connection.reconnectAttempts}`
    : connection.isLive
      ? `${formatCount(connection.connectedClients)} clients · ${formatLagMs(connection.lastFrameAgoMs)} ago`
      : connection.hasError
        ? "Stream failed"
        : "Awaiting connection";
  return (
    <MetricsCard
      id="connection-status"
      label="Stream"
      intent={intent}
      value={connection.label}
      trailing={
        <MetricsBadge
          intent={intent}
          pulse={connection.isLive}
          ariaLabel={`Stream phase ${connection.phase}`}
        >
          {connection.phase}
        </MetricsBadge>
      }
      detail={detail}
    />
  );
}

export const ConnectionStatusCard = memo(ConnectionStatusCardImpl);
