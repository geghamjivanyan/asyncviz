/**
 * Severity / lifecycle-state badge.
 *
 * One component for both axes — they share the same visual treatment
 * (small uppercase pill). The intent prop drives the palette mapping
 * via :func:`intentToken`.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import type {
  BlockingGroupSeverity,
  BlockingGroupState,
  BlockingWarningIntent,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import {
  intentToken,
  severityBadgeLabel,
  stateBadgeLabel,
} from "@/dashboard/warnings/blocking/utils/formatting";

export interface BlockingWarningSeverityBadgeProps {
  severity: BlockingGroupSeverity;
  intent: BlockingWarningIntent;
  className?: string;
}

function BlockingWarningSeverityBadgeImpl({
  severity,
  intent,
  className,
}: BlockingWarningSeverityBadgeProps) {
  return (
    <Badge
      intent={intentToken(intent)}
      aria-label={`Severity: ${severityBadgeLabel(severity)}`}
      className={className}
    >
      {severityBadgeLabel(severity)}
    </Badge>
  );
}

export const BlockingWarningSeverityBadge = memo(BlockingWarningSeverityBadgeImpl);

export interface BlockingWarningStateBadgeProps {
  state: BlockingGroupState;
  intent: BlockingWarningIntent;
  className?: string;
}

function BlockingWarningStateBadgeImpl({
  state,
  intent,
  className,
}: BlockingWarningStateBadgeProps) {
  return (
    <Badge
      intent={intentToken(intent)}
      aria-label={`State: ${stateBadgeLabel(state)}`}
      className={className}
    >
      {stateBadgeLabel(state)}
    </Badge>
  );
}

export const BlockingWarningStateBadge = memo(BlockingWarningStateBadgeImpl);
