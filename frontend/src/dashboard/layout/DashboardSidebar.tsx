/**
 * Canonical dashboard sidebar.
 *
 * Today renders the project-level navigation links so the dashboard
 * has a stable side rail. Future iterations stack route-aware widgets
 * (task tree, runtime selector, saved replay sessions) into the same
 * region.
 *
 * The sidebar collapses via :class:`DashboardLayoutContext`. When
 * collapsed it stays mounted but rendered narrow so route-active
 * indicators don't churn on every toggle.
 */

import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";
import { NAVIGABLE_ROUTES, ROUTES } from "@/app/routing/routes";
import { useDashboardLayout } from "@/dashboard/layout/context/DashboardLayoutContext";
import { cn } from "@/lib/cn";

export interface DashboardSidebarProps {
  /** Optional content rendered below the navigation block. */
  children?: ReactNode;
  className?: string;
}

export function DashboardSidebar({ children, className }: DashboardSidebarProps) {
  const { sidebar } = useDashboardLayout();
  if (sidebar === "hidden") return null;
  const collapsed = sidebar === "collapsed";
  return (
    <aside
      role="complementary"
      aria-label="Navigation"
      className={cn(
        "flex min-h-0 shrink-0 flex-col border-r border-line bg-panel transition-all",
        collapsed ? "w-12" : "w-56",
        className,
      )}
    >
      <nav role="navigation" aria-label="Routes" className="flex flex-col gap-1 p-2 text-xs">
        {NAVIGABLE_ROUTES.map((route) => (
          <NavLink
            key={route.path}
            to={route.path}
            end={route.path === ROUTES.overview}
            title={route.description}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded px-2 py-1.5 font-mono uppercase tracking-wider transition-colors",
                isActive
                  ? "bg-elevated text-accent"
                  : "text-muted hover:bg-elevated hover:text-text",
                collapsed && "justify-center px-0",
              )
            }
          >
            <span aria-hidden className="text-[0.55rem]">
              {route.label.slice(0, 2).toUpperCase()}
            </span>
            {!collapsed && <span>{route.label}</span>}
          </NavLink>
        ))}
      </nav>
      {!collapsed && children !== undefined && (
        <div className="flex min-h-0 flex-1 flex-col border-t border-line">{children}</div>
      )}
    </aside>
  );
}
