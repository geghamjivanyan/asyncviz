/**
 * Records every route change into :class:`ClientMetrics`.
 *
 * Mounted once by :class:`DashboardLayout`; nothing else should call
 * it. The hook listens to ``useLocation`` and emits one
 * ``recordNavigation`` per distinct pathname transition.
 */

import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useClientMetrics } from "@/app/providers/RuntimeProvider";

export function useNavigationObservability(): void {
  const metrics = useClientMetrics();
  const { pathname } = useLocation();
  const lastPath = useRef<string | null>(null);
  useEffect(() => {
    if (lastPath.current === pathname) return;
    lastPath.current = pathname;
    metrics.recordNavigation(pathname);
  }, [metrics, pathname]);
}
