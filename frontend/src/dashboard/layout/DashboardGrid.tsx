/**
 * Inner grid for the dashboard frame.
 *
 * Owns the horizontal axis: sidebar on the left, primary content in
 * the middle, optional ``aside`` on the right (Inspector-style
 * panels). Each region is a flex slot so child layouts (split views,
 * panel stacks) can compose freely.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface DashboardGridProps {
  /** Left-side rail; rendered first inside the grid. */
  sidebar?: ReactNode;
  /** Primary content area. Required. */
  content: ReactNode;
  /** Optional right-side rail (Inspector / details panels). */
  aside?: ReactNode;
  className?: string;
}

export function DashboardGrid({ sidebar, content, aside, className }: DashboardGridProps) {
  return (
    <div className={cn("flex min-h-0 min-w-0 flex-1", className)}>
      {sidebar}
      {content}
      {aside}
    </div>
  );
}
