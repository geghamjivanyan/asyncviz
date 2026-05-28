/**
 * Connection / replay status indicator for the panel header.
 *
 * Shows whether the panel is reading from a live websocket stream
 * (default) or a replay session. Today the indicator just reports the
 * runtime store's connection phase + the panel's own hydration status;
 * future replay integration will pivot this to a replay-aware label.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { useConnectionPhase } from "@/state/runtime";
import { isLivePhase } from "@/runtime/websocket";

export interface BlockingWarningReplayBadgeProps {
  status: "idle" | "loading" | "ready" | "error";
  errorMessage: string | null;
  className?: string;
}

function BlockingWarningReplayBadgeImpl({
  status,
  errorMessage,
  className,
}: BlockingWarningReplayBadgeProps) {
  const phase = useConnectionPhase();
  if (status === "error") {
    return (
      <Badge intent="danger" aria-label={`Hydration error: ${errorMessage ?? "unknown"}`} className={className}>
        Error
      </Badge>
    );
  }
  if (status === "loading") {
    return (
      <Badge intent="default" aria-label="Hydrating warnings" className={className}>
        Loading
      </Badge>
    );
  }
  if (isLivePhase(phase)) {
    return (
      <Badge intent="success" aria-label="Live stream connected" className={className}>
        Live
      </Badge>
    );
  }
  return (
    <Badge intent="default" aria-label={`Connection ${phase}`} className={className}>
      {phase}
    </Badge>
  );
}

export const BlockingWarningReplayBadge = memo(BlockingWarningReplayBadgeImpl);
