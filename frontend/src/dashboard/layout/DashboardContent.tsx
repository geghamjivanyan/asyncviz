/**
 * Main content region for the dashboard.
 *
 * A thin wrapper around :class:`DashboardRegion` that pins the
 * ``role="main"`` semantic and grows to fill the remaining column
 * width between the sidebar and the right-side rail. Pages render
 * inside this region via :class:`Outlet` or direct composition.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface DashboardContentProps {
  children: ReactNode;
  className?: string;
}

export function DashboardContent({ children, className }: DashboardContentProps) {
  return (
    <main
      role="main"
      aria-label="Dashboard content"
      className={cn("flex min-h-0 min-w-0 flex-1 flex-col", className)}
    >
      {children}
    </main>
  );
}
