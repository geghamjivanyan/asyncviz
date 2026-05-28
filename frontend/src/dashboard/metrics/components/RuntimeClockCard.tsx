/**
 * Runtime-clock card — uptime + connected clients.
 */

import { memo } from "react";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
import { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
import { formatCount, formatUptime } from "@/dashboard/metrics/utils/format";
import type { RuntimeClockSummary } from "@/dashboard/metrics/models/summary";
import type { ConnectionSummary } from "@/dashboard/metrics/models/summary";

export interface RuntimeClockCardProps {
  clock: RuntimeClockSummary;
  connection: ConnectionSummary;
}

function RuntimeClockCardImpl({ clock, connection }: RuntimeClockCardProps) {
  const uptime = clock.uptimeSeconds > 0 ? clock.uptimeSeconds : clock.serverUptimeSeconds;
  return (
    <MetricsCard
      id="runtime-clock"
      label="Uptime"
      value={formatUptime(uptime)}
      trailing={
        <MetricsBadge
          intent="default"
          ariaLabel={`Connected clients ${connection.connectedClients}`}
        >
          {formatCount(connection.connectedClients)} ws
        </MetricsBadge>
      }
      detail={uptime > 0 ? "Since runtime start" : "Awaiting heartbeat"}
    />
  );
}

export const RuntimeClockCard = memo(RuntimeClockCardImpl);
