/**
 * Compact label for status / counts.
 */

import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { INTENT_BORDER, TEXT_PALETTE } from "@/ui/theme/tokens";
import type { Intent } from "@/ui/theme/tokens";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  intent?: Intent;
  children: ReactNode;
}

const INTENT_TEXT: Record<Intent, (typeof TEXT_PALETTE)[keyof typeof TEXT_PALETTE]> = {
  default: TEXT_PALETTE.muted,
  accent: TEXT_PALETTE.accent,
  success: TEXT_PALETTE.success,
  warning: TEXT_PALETTE.warning,
  danger: TEXT_PALETTE.danger,
};

export function Badge({ intent = "default", className, children, ...rest }: BadgeProps) {
  return (
    <span
      {...rest}
      className={cn(
        "inline-flex items-center rounded border bg-elevated px-2 py-0.5 font-mono text-xs uppercase tracking-wider",
        INTENT_BORDER[intent],
        INTENT_TEXT[intent],
        className,
      )}
    >
      {children}
    </span>
  );
}
