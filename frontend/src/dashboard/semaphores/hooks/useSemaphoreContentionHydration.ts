/**
 * Hydration hook for the semaphore contention panel.
 *
 * Fetches ``GET /api/semaphores`` once on mount and folds the
 * snapshot into :class:`SemaphoreContentionStore`. Tests inject a stub
 * fetcher via ``options.fetcher``.
 */

import { useEffect } from "react";
import { useRuntimeConfig } from "@/app/providers/ConfigProvider";
import { useClientMetrics } from "@/app/providers/RuntimeProvider";
import { useSemaphoreContentionStore } from "@/dashboard/semaphores/SemaphoreContentionStore";
import { getSemaphoreContentionPanelMetrics } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionMetricsCollector";
import { recordSemaphoreContentionTrace } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionTracing";
import type { SemaphoreHydrationResponse } from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export interface SemaphoreContentionHydrationOptions {
  enabled?: boolean;
  fetcher?: typeof fetch;
}

export function semaphoreContentionSnapshotUrl(apiBaseUrl: string): string {
  const base = apiBaseUrl.replace(/\/+$/, "");
  return `${base}/api/semaphores`;
}

export function useSemaphoreContentionHydration(
  options: SemaphoreContentionHydrationOptions = {},
): void {
  const { enabled = true, fetcher = typeof fetch === "function" ? fetch : undefined } = options;
  const config = useRuntimeConfig();
  const clientMetrics = useClientMetrics();
  const hydrateSnapshot = useSemaphoreContentionStore((s) => s.hydrateSnapshot);
  const markLoading = useSemaphoreContentionStore((s) => s.markLoading);
  const markError = useSemaphoreContentionStore((s) => s.markError);

  useEffect(() => {
    if (!enabled) return undefined;
    if (fetcher === undefined) {
      markError("fetch is not available in this environment");
      return undefined;
    }
    const controller = new AbortController();
    const panelMetrics = getSemaphoreContentionPanelMetrics();
    markLoading();
    const url = semaphoreContentionSnapshotUrl(config.apiBaseUrl);
    (async () => {
      try {
        const response = await fetcher(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} ${response.statusText}`);
        }
        const payload = (await response.json()) as SemaphoreHydrationResponse;
        hydrateSnapshot(payload);
        clientMetrics.recordSnapshotHydration();
        panelMetrics.recordHydration();
        recordSemaphoreContentionTrace({
          kind: "snapshot-fetched",
          detail: `semaphores=${payload.semaphores.length}`,
        });
      } catch (cause) {
        if (controller.signal.aborted) return;
        const message = cause instanceof Error ? cause.message : String(cause);
        markError(message);
        clientMetrics.recordSnapshotHydrationFailure();
        panelMetrics.recordHydrationFailure();
        recordSemaphoreContentionTrace({
          kind: "snapshot-failed",
          detail: message,
        });
      }
    })();
    return () => controller.abort();
  }, [enabled, fetcher, config.apiBaseUrl, hydrateSnapshot, markLoading, markError, clientMetrics]);
}
