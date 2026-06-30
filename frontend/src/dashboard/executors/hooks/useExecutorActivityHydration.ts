/**
 * Hydration hook for the executor activity panel.
 *
 * Fetches ``GET /api/executor/metrics`` once on mount + folds the
 * snapshot into :class:`ExecutorActivityStore`.
 */

import { useEffect } from "react";
import { useRuntimeConfig } from "@/app/providers/ConfigProvider";
import { useClientMetrics } from "@/app/providers/RuntimeProvider";
import { useExecutorActivityStore } from "@/dashboard/executors/ExecutorActivityStore";
import { getExecutorActivityPanelMetrics } from "@/dashboard/executors/diagnostics/ExecutorActivityMetricsCollector";
import { recordExecutorActivityTrace } from "@/dashboard/executors/diagnostics/ExecutorActivityTracing";
import type { ExecutorActivityHydrationResponse } from "@/dashboard/executors/models/ExecutorActivityModels";

export interface ExecutorActivityHydrationOptions {
  enabled?: boolean;
  fetcher?: typeof fetch;
}

export function executorActivitySnapshotUrl(apiBaseUrl: string): string {
  const base = apiBaseUrl.replace(/\/+$/, "");
  return `${base}/api/executor/metrics`;
}

export function useExecutorActivityHydration(options: ExecutorActivityHydrationOptions = {}): void {
  const { enabled = true, fetcher = typeof fetch === "function" ? fetch : undefined } = options;
  const config = useRuntimeConfig();
  const clientMetrics = useClientMetrics();
  const hydrateSnapshot = useExecutorActivityStore((s) => s.hydrateSnapshot);
  const markLoading = useExecutorActivityStore((s) => s.markLoading);
  const markError = useExecutorActivityStore((s) => s.markError);

  useEffect(() => {
    if (!enabled) return undefined;
    if (fetcher === undefined) {
      markError("fetch is not available in this environment");
      return undefined;
    }
    const controller = new AbortController();
    const panelMetrics = getExecutorActivityPanelMetrics();
    markLoading();
    const url = executorActivitySnapshotUrl(config.apiBaseUrl);
    (async () => {
      try {
        const response = await fetcher(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} ${response.statusText}`);
        }
        const payload = (await response.json()) as ExecutorActivityHydrationResponse;
        hydrateSnapshot(payload);
        clientMetrics.recordSnapshotHydration();
        panelMetrics.recordHydration();
        recordExecutorActivityTrace({
          kind: "snapshot-fetched",
          detail: `executors=${payload.executors.length}`,
        });
      } catch (cause) {
        if (controller.signal.aborted) return;
        const message = cause instanceof Error ? cause.message : String(cause);
        markError(message);
        clientMetrics.recordSnapshotHydrationFailure();
        panelMetrics.recordHydrationFailure();
        recordExecutorActivityTrace({ kind: "snapshot-failed", detail: message });
      }
    })();
    return () => controller.abort();
  }, [enabled, fetcher, config.apiBaseUrl, hydrateSnapshot, markLoading, markError, clientMetrics]);
}
