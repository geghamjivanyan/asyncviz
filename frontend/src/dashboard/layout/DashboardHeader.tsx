/**
 * Canonical dashboard header.
 *
 * Consolidates the legacy ``Toolbar`` + the prior ``DashboardShell``
 * header into a single composition. Renders the brand, the navigation
 * strip, the canonical :class:`ConnectionStatusContainer` (replacing
 * the legacy connection badge), the runtime-status badge, and the
 * sidebar toggle. Slots are exposed via props so future toolbar
 * widgets (metrics ticker, runtime selector) can plug in without
 * forking the component.
 */

import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";
import { NAVIGABLE_ROUTES, ROUTES } from "@/app/routing/routes";
import { useRuntimeConnection } from "@/hooks/useRuntimeConnection";
import { useRuntimeStatus } from "@/state/runtime";
import { useDashboardLayout } from "@/dashboard/layout/context/DashboardLayoutContext";
import { Badge } from "@/ui/primitives/Badge";
import { cn } from "@/lib/cn";
import { ConnectionStatusContainer } from "@/dashboard/connection";

export interface DashboardHeaderProps {
  /** Left-aligned slot. Defaults to the canonical brand block. */
  brand?: ReactNode;
  /** Right-aligned content rendered before the action button. */
  actions?: ReactNode;
  /** Whether to render the navigation strip. */
  showNav?: boolean;
  className?: string;
}

export function DashboardHeader({
  brand,
  actions,
  showNav = true,
  className,
}: DashboardHeaderProps) {
  const { connection, connect, disconnect } = useRuntimeConnection();
  const status = useRuntimeStatus();
  const { sidebar, toggleSidebar } = useDashboardLayout();
  const isLive = connection === "open" || connection === "connecting";

  return (
    <header
      role="banner"
      className={cn(
        "flex h-12 shrink-0 items-center justify-between gap-4 border-b border-line bg-panel px-4",
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          aria-label={sidebar === "expanded" ? "Collapse sidebar" : "Expand sidebar"}
          aria-pressed={sidebar !== "expanded"}
          onClick={toggleSidebar}
          className="rounded border border-line bg-elevated px-2 py-1 font-mono text-xs text-muted transition-colors hover:border-accent hover:text-accent"
        >
          {sidebar === "expanded" ? "◀" : "▶"}
        </button>
        {brand ?? <DashboardBrand />}
      </div>

      {showNav && (
        <nav role="navigation" aria-label="Primary" className="flex items-center gap-3 text-xs">
          {NAVIGABLE_ROUTES.map((route) => (
            <NavLink
              key={route.path}
              to={route.path}
              end={route.path === ROUTES.overview}
              className={({ isActive }) =>
                cn(
                  "rounded px-2 py-0.5 font-mono uppercase tracking-wider transition-colors",
                  isActive ? "text-accent" : "text-muted hover:text-text",
                )
              }
            >
              {route.label}
            </NavLink>
          ))}
        </nav>
      )}

      <div className="flex items-center gap-3">
        {actions}
        <Badge intent="default" aria-label={`Runtime status: ${status}`}>
          {status}
        </Badge>
        <ConnectionStatusContainer />
        <button
          type="button"
          onClick={isLive ? disconnect : connect}
          className="rounded border border-line bg-elevated px-2.5 py-1 text-xs text-text transition-colors hover:border-accent hover:text-accent"
        >
          {isLive ? "Disconnect" : "Connect"}
        </button>
      </div>
    </header>
  );
}

function DashboardBrand() {
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-sm tracking-wide text-text">AsyncViz</span>
      <span className="text-xs uppercase tracking-widest text-subtle">runtime</span>
    </div>
  );
}
