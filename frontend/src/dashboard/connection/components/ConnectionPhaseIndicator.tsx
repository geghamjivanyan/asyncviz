/**
 * Phase indicator — label + reconnect count + visibility intent.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import { TEXT_PALETTE } from "@/ui/theme/tokens";
import type { ConnectionPhaseSummary, ReconnectSummary } from "@/dashboard/connection/models/state";

const VISIBILITY_TEXT: Record<ConnectionPhaseSummary["visibility"], string> = {
  live: TEXT_PALETTE.success,
  transitional: TEXT_PALETTE.warning,
  offline: TEXT_PALETTE.subtle,
  error: TEXT_PALETTE.danger,
};

export interface ConnectionPhaseIndicatorProps {
  phase: ConnectionPhaseSummary;
  reconnect: ReconnectSummary;
}

function ConnectionPhaseIndicatorImpl({ phase, reconnect }: ConnectionPhaseIndicatorProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={`Connection phase ${phase.label}`}
      data-connection-phase={phase.phase}
      className="flex min-w-0 items-center gap-2 font-mono text-xs"
    >
      <span className={cn("uppercase tracking-widest", VISIBILITY_TEXT[phase.visibility])}>
        {phase.label}
      </span>
      {reconnect.attempts > 0 && (
        <span
          aria-label={`Reconnect attempts ${reconnect.attempts}`}
          className={cn(
            "rounded border border-line px-1.5 py-0.5 text-[10px] uppercase tracking-widest",
            reconnect.isFlaky ? TEXT_PALETTE.danger : TEXT_PALETTE.warning,
          )}
        >
          retry {reconnect.attempts}
        </span>
      )}
    </div>
  );
}

export const ConnectionPhaseIndicator = memo(ConnectionPhaseIndicatorImpl);
