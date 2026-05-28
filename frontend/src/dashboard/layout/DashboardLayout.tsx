/**
 * Canonical dashboard layout composition root.
 *
 * Composition contract::
 *
 *   <DashboardLayout>
 *     // implicitly wraps everything in:
 *     // <DashboardLayoutProvider>
 *     //   <header> ← DashboardHeader (default unless `header` slot set)
 *     //   <MetricsHeader> ← MetricsHeaderContainer (default; pass null to hide)
 *     //   <DashboardGrid sidebar={...} content={children} aside={...}>
 *     //   <DashboardStatusBar />
 *     // </DashboardLayoutProvider>
 *
 * Pages use this as either:
 *
 *   1. The default frame around their content — pass children + an
 *      optional ``aside``. The shell takes care of the header,
 *      metrics band, sidebar, and status bar.
 *   2. A *custom* frame — override ``header``, ``metrics``, ``sidebar``,
 *      or ``footer`` slots. The Overview page does this to inline its
 *      own inspector rail in the same row as the timeline + event
 *      panels.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { DashboardLayoutProvider } from "@/dashboard/layout/context/DashboardLayoutContext";
import type { DashboardLayoutState } from "@/dashboard/layout/models/layoutState";
import { DashboardHeader } from "@/dashboard/layout/DashboardHeader";
import { DashboardSidebar } from "@/dashboard/layout/DashboardSidebar";
import { DashboardContent } from "@/dashboard/layout/DashboardContent";
import { DashboardStatusBar } from "@/dashboard/layout/DashboardStatusBar";
import { DashboardGrid } from "@/dashboard/layout/DashboardGrid";
import { MetricsHeaderContainer } from "@/dashboard/metrics/components/MetricsHeaderContainer";

export interface DashboardLayoutProps {
  /** Override the header. Pass ``null`` to hide it entirely. */
  header?: ReactNode;
  /** Override the runtime-metrics band. Pass ``null`` to hide it. */
  metrics?: ReactNode;
  /** Override the sidebar. Pass ``null`` to hide it entirely. */
  sidebar?: ReactNode;
  /** Right-side rail (Inspector-style content). */
  aside?: ReactNode;
  /** Override the bottom status bar. Pass ``null`` to hide it. */
  footer?: ReactNode;
  /** Initial layout state — used by tests + by route pages that want
   *  to start with a collapsed sidebar. */
  initialState?: Partial<DashboardLayoutState>;
  className?: string;
  children: ReactNode;
}

export function DashboardLayout({
  header,
  metrics,
  sidebar,
  aside,
  footer,
  initialState,
  className,
  children,
}: DashboardLayoutProps) {
  const renderedHeader = header === undefined ? <DashboardHeader /> : header;
  const renderedMetrics = metrics === undefined ? <MetricsHeaderContainer /> : metrics;
  const renderedSidebar = sidebar === undefined ? <DashboardSidebar /> : sidebar;
  const renderedFooter = footer === undefined ? <DashboardStatusBar /> : footer;
  return (
    <DashboardLayoutProvider initialState={initialState}>
      <div
        className={cn(
          "flex h-screen min-h-0 flex-col bg-canvas text-text",
          "selection:bg-accent/30",
          className,
        )}
      >
        {renderedHeader}
        {renderedMetrics}
        <DashboardGrid
          sidebar={renderedSidebar}
          content={<DashboardContent>{children}</DashboardContent>}
          aside={aside}
        />
        {renderedFooter}
      </div>
    </DashboardLayoutProvider>
  );
}
