/**
 * Compact badge used inside metrics cards.
 *
 * Wraps the canonical :class:`Badge` primitive with metrics-card
 * defaults — extra tight, mono font, with an optional pulse dot for
 * "live" states.
 */

import { Badge } from "@/ui/primitives/Badge";
import { cn } from "@/lib/cn";
import type { Intent } from "@/ui/theme/tokens";
import type { ReactNode } from "react";

export interface MetricsBadgeProps {
  intent?: Intent;
  pulse?: boolean;
  children: ReactNode;
  ariaLabel?: string;
}

const PULSE_COLOR: Record<Intent, string> = {
  default: "bg-subtle",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};

export function MetricsBadge({
  intent = "default",
  pulse = false,
  children,
  ariaLabel,
}: MetricsBadgeProps) {
  return (
    <Badge intent={intent} aria-label={ariaLabel}>
      {pulse && (
        <span
          aria-hidden="true"
          className={cn("mr-1.5 inline-block h-1.5 w-1.5 rounded-full", PULSE_COLOR[intent])}
        />
      )}
      {children}
    </Badge>
  );
}
