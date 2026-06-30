/**
 * Hydration hook for the queue pressure panel.
 *
 * Fetches ``GET /api/queues/metrics`` once on mount + folds the
 * snapshot into :class:`QueuePressureStore`. Tests inject a stub
 * fetcher via :type:`HydrationOptions.fetcher`. No retry loop today
 * — the panel re-mounts on navigation, which is the natural retry.
 */

import { useEffect } from "react";
import { useRuntimeConfig } from "@/app/providers/ConfigProvider";
import { useClientMetrics } from "@/app/providers/RuntimeProvider";
import { useQueuePressureStore } from "@/dashboard/queues/QueuePressureStore";
import { getQueuePressurePanelMetrics } from "@/dashboard/queues/diagnostics/QueuePressureMetricsCollector";
import { recordQueuePressureTrace } from "@/dashboard/queues/diagnostics/QueuePressureTracing";
import type { QueueMetricsHydrationResponse } from "@/dashboard/queues/models/QueuePressureModels";

export interface QueuePressureHydrationOptions {
  enabled?: boolean;
  fetcher?: typeof fetch;
}

export function queuePressureSnapshotUrl(apiBaseUrl: string): string {
  const base = apiBaseUrl.replace(/\/+$/, "");
  return `${base}/api/queues/metrics`;
}

export function useQueuePressureHydration(options: QueuePressureHydrationOptions = {}): void {
  const { enabled = true, fetcher = typeof fetch === "function" ? fetch : undefined } = options;
  const config = useRuntimeConfig();
  const clientMetrics = useClientMetrics();
  const hydrateSnapshot = useQueuePressureStore((s) => s.hydrateSnapshot);
  const markLoading = useQueuePressureStore((s) => s.markLoading);
  const markError = useQueuePressureStore((s) => s.markError);

  useEffect(() => {
    if (!enabled) return undefined;
    if (fetcher === undefined) {
      markError("fetch is not available in this environment");
      return undefined;
    }
    const controller = new AbortController();
    const panelMetrics = getQueuePressurePanelMetrics();
    markLoading();
    const url = queuePressureSnapshotUrl(config.apiBaseUrl);
    (async () => {
      try {
        const response = await fetcher(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} ${response.statusText}`);
        }
        const payload = (await response.json()) as QueueMetricsHydrationResponse;
        hydrateSnapshot(payload);
        clientMetrics.recordSnapshotHydration();
        panelMetrics.recordHydration();
        recordQueuePressureTrace({
          kind: "snapshot-fetched",
          detail: `queues=${payload.queues.length}`,
        });
      } catch (cause) {
        if (controller.signal.aborted) return;
        const message = cause instanceof Error ? cause.message : String(cause);
        markError(message);
        clientMetrics.recordSnapshotHydrationFailure();
        panelMetrics.recordHydrationFailure();
        recordQueuePressureTrace({ kind: "snapshot-failed", detail: message });
      }
    })();
    return () => controller.abort();
  }, [enabled, fetcher, config.apiBaseUrl, hydrateSnapshot, markLoading, markError, clientMetrics]);
}
