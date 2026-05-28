/**
 * Overflow-safe rendering region.
 *
 * A "region" is the smallest layout unit that pins a content area to
 * the surrounding flex container. The component does three things:
 *
 *   1. Clamps to ``min-h-0`` / ``min-w-0`` so flex children can shrink
 *      without overflowing.
 *   2. Optionally scrolls (``scroll="auto"`` by default; ``scroll="none"``
 *      for regions that own a virtualization scroller themselves).
 *   3. Stamps the canonical ``role="region"`` for accessibility plus
 *      an ``aria-label`` from the ``label`` prop.
 *
 * Every panel-level container in :class:`DashboardLayout` is a
 * :class:`DashboardRegion`; consumers compose region + panel rather
 * than open-coding flex / overflow plumbing.
 */

import { forwardRef } from "react";
import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export type RegionScroll = "auto" | "y" | "x" | "none";

export interface DashboardRegionProps extends HTMLAttributes<HTMLDivElement> {
  /** ``role="region"`` ``aria-label`` value. */
  label: string;
  /** Scroll behavior; defaults to ``auto`` (both axes). */
  scroll?: RegionScroll;
  /** Pass through when the region is part of a flex column / row. */
  grow?: boolean;
  children: ReactNode;
}

const SCROLL_CLASSES: Record<RegionScroll, string> = {
  auto: "overflow-auto",
  y: "overflow-y-auto overflow-x-hidden",
  x: "overflow-x-auto overflow-y-hidden",
  none: "overflow-hidden",
};

export const DashboardRegion = forwardRef<HTMLDivElement, DashboardRegionProps>(
  function DashboardRegion(
    { label, scroll = "auto", grow = false, className, children, ...rest },
    ref,
  ) {
    return (
      <div
        ref={ref}
        role="region"
        aria-label={label}
        {...rest}
        className={cn(
          "flex min-h-0 min-w-0 flex-col",
          grow && "flex-1",
          SCROLL_CLASSES[scroll],
          className,
        )}
      >
        {children}
      </div>
    );
  },
);
