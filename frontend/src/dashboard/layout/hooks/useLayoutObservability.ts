/**
 * Layout-side observability hook.
 *
 * Each panel that mounts inside :class:`DashboardLayout` calls this
 * with its panel id; the hook records the mount duration into
 * :class:`ClientMetrics` so the diagnostics page can surface slow-
 * mounting panels.
 *
 * The hook intentionally does not measure re-renders — that's a
 * harder profile to define cleanly, and the data isn't useful for
 * operational dashboards without further aggregation. Mount latency
 * is the right initial signal.
 */

import { useEffect } from "react";
import { useClientMetrics } from "@/app/providers/RuntimeProvider";

export function useLayoutObservability(panelId: string): void {
  const metrics = useClientMetrics();
  useEffect(() => {
    const start = performance.now();
    // Schedule a microtask after the initial paint commits so the
    // measurement reflects mount-to-paint latency rather than just
    // synchronous render time.
    const handle = window.requestAnimationFrame(() => {
      const duration = performance.now() - start;
      metrics.recordPanelMount(panelId, duration);
    });
    return () => window.cancelAnimationFrame(handle);
  }, [metrics, panelId]);
}
