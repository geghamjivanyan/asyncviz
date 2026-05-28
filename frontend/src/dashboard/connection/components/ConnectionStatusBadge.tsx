/**
 * Compact badge — the visible footprint in dashboard chrome.
 *
 * Maps the canonical :type:`ConnectionVisibility` (live / transitional
 * / offline / error) to one of the design-system intents.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import type { Intent } from "@/ui/theme/tokens";
import type { ConnectionPhaseSummary } from "@/dashboard/connection/models/state";
import { cn } from "@/lib/cn";

const VISIBILITY_INTENT: Record<ConnectionPhaseSummary["visibility"], Intent> = {
  live: "success",
  transitional: "warning",
  offline: "default",
  error: "danger",
};

const PULSE_COLOR: Record<Intent, string> = {
  default: "bg-subtle",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};

export interface ConnectionStatusBadgeProps {
  phase: ConnectionPhaseSummary;
  /** Render a tighter label suitable for inline header use. */
  compact?: boolean;
}

function ConnectionStatusBadgeImpl({ phase, compact = false }: ConnectionStatusBadgeProps) {
  const intent = VISIBILITY_INTENT[phase.visibility];
  const label = compact ? phase.phase : phase.label;
  return (
    <Badge
      intent={intent}
      aria-label={`Connection ${phase.label}`}
      data-connection-phase={phase.phase}
    >
      <span
        aria-hidden="true"
        className={cn(
          "mr-1.5 inline-block h-1.5 w-1.5 rounded-full",
          PULSE_COLOR[intent],
          phase.isLive && "animate-pulse",
        )}
      />
      {label}
    </Badge>
  );
}

export const ConnectionStatusBadge = memo(ConnectionStatusBadgeImpl);
