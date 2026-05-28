/**
 * Inline status indicator — dot + label.
 *
 * Used inside cards where a badge would be too heavy (compact phase
 * row, replay-window indicator).
 */

import { cn } from "@/lib/cn";
import type { Intent } from "@/ui/theme/tokens";
import { TEXT_PALETTE } from "@/ui/theme/tokens";

export interface MetricsStatusProps {
  intent?: Intent;
  label: string;
  ariaLabel?: string;
}

const DOT_COLOR: Record<Intent, string> = {
  default: "bg-subtle",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};

const INTENT_TEXT: Record<Intent, string> = {
  default: TEXT_PALETTE.muted,
  accent: TEXT_PALETTE.accent,
  success: TEXT_PALETTE.success,
  warning: TEXT_PALETTE.warning,
  danger: TEXT_PALETTE.danger,
};

export function MetricsStatus({ intent = "default", label, ariaLabel }: MetricsStatusProps) {
  return (
    <span
      role="status"
      aria-label={ariaLabel ?? label}
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest",
        INTENT_TEXT[intent],
      )}
    >
      <span
        aria-hidden="true"
        className={cn("inline-block h-1.5 w-1.5 rounded-full", DOT_COLOR[intent])}
      />
      {label}
    </span>
  );
}
