/**
 * Application shell that wraps every routed page.
 *
 * The shell delegates the entire frame to :class:`DashboardLayout`
 * (the canonical composition root) and renders the route :class:`Outlet`
 * inside it. Pages that need custom chrome compose their own
 * :class:`DashboardLayout` instance with overridden slots — see
 * :class:`OverviewPage` for the inspector-rail example.
 *
 * Also drives navigation observability — every route change increments
 * :class:`ClientMetrics.navigationsTotal`.
 */

import { Outlet, useLocation } from "react-router-dom";
import { DashboardLayout } from "@/dashboard/layout";
import { useNavigationObservability } from "@/dashboard/layout/hooks/useNavigationObservability";
import { useDashboardAutoConnect } from "@/hooks/useDashboardAutoConnect";
import { ROUTES } from "@/app/routing/routes";

export function DashboardShell() {
  const { pathname } = useLocation();
  // The Overview page composes its own ``DashboardLayout`` instance
  // (it needs the right-side Inspector rail). Pass straight through
  // so the page owns the entire frame and we don't double-render the
  // layout chrome.
  if (pathname === ROUTES.overview) {
    return (
      <>
        <ShellInstrumentation />
        <Outlet />
      </>
    );
  }
  return (
    <DashboardLayout>
      <ShellInstrumentation />
      <Outlet />
    </DashboardLayout>
  );
}

/**
 * Tiny no-render component that wires shell-level effects:
 *
 *   * Navigation observability — every route change increments
 *     :class:`ClientMetrics.navigationsTotal`.
 *   * Runtime auto-connect — opens the realtime websocket on shell
 *     mount and tears it down on unmount. See
 *     :func:`useDashboardAutoConnect` for the rationale (the
 *     underlying :func:`useRuntimeConnection` stays opt-in for
 *     non-dashboard consumers).
 *
 * Lives as a separate component so the hooks can run inside the
 * :class:`DashboardLayout` provider tree.
 */
function ShellInstrumentation(): null {
  useNavigationObservability();
  useDashboardAutoConnect();
  return null;
}
