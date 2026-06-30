/**
 * Section component for a bucket of warnings (active / recent).
 *
 * Renders the heading + an accessible-region wrapper. Virtualization
 * is delegated to :class:`BlockingWarningVirtualization`; this
 * component just lays out the section semantics so the panel layout
 * stays declarative.
 */

import { memo, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface BlockingWarningGroupingProps {
  id: string;
  title: string;
  count: number;
  emptyLabel: string;
  children: ReactNode;
  className?: string;
}

function BlockingWarningGroupingImpl({
  id,
  title,
  count,
  emptyLabel,
  children,
  className,
}: BlockingWarningGroupingProps) {
  return (
    <section
      aria-labelledby={id}
      className={cn("flex flex-col gap-2", className)}
      data-testid={`blocking-warning-section-${id}`}
    >
      <header className="flex items-center gap-2">
        <h3 id={id} className="font-mono text-xs uppercase tracking-wider text-subtle">
          {title}
        </h3>
        <span className="font-mono text-xs text-text" aria-label={`${count} warnings in ${title}`}>
          {count}
        </span>
      </header>
      {count === 0 ? (
        <p
          className="text-subtle text-xs italic"
          data-testid={`blocking-warning-section-${id}-empty`}
        >
          {emptyLabel}
        </p>
      ) : (
        children
      )}
    </section>
  );
}

export const BlockingWarningGrouping = memo(BlockingWarningGroupingImpl);
