/**
 * Bordered surface for panel-style content.
 *
 * Use ``intent`` to mark status-bearing cards (warnings, errors).
 * ``padding`` follows the :data:`SPACING` scale.
 */

import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { INTENT_BORDER, SPACING } from "@/ui/theme/tokens";
import type { Intent, Spacing } from "@/ui/theme/tokens";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  intent?: Intent;
  padding?: Spacing;
  children: ReactNode;
}

export function Card({
  intent = "default",
  padding = "md",
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <div
      {...rest}
      className={cn(
        "rounded border bg-panel text-text",
        INTENT_BORDER[intent],
        SPACING[padding],
        className,
      )}
    >
      {children}
    </div>
  );
}
