/**
 * Hydration hook for the blocking-warning panel.
 *
 * Fetches ``GET /api/runtime/warnings/blocking`` once on mount and
 * folds the snapshot into :class:`BlockingWarningStore`. Tests inject a
 * stub fetcher via :type:`HydrationOptions.fetcher`.
 *
 * No retry loop today — the panel re-mounts on navigation, which is
 * the natural retry. Future work can add a retry-with-backoff option
 * if operators need it for flaky networks.
 */

import { useEffect } from "react";
import { useRuntimeConfig } from "@/app/providers/ConfigProvider";
import { useClientMetrics } from "@/app/providers/RuntimeProvider";
import type { BlockingWarningEmitterSnapshot } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import { recordBlockingWarningTrace } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";
import { getBlockingWarningPanelMetrics } from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";

export interface BlockingWarningHydrationOptions {
  /** Skip hydration entirely — useful for tests that hand-feed the store. */
  enabled?: boolean;
  /** Test-only override; defaults to global ``fetch``. */
  fetcher?: typeof fetch;
}

/** Build the snapshot endpoint URL from the runtime config. */
export function blockingWarningSnapshotUrl(apiBaseUrl: string): string {
  // ``apiBaseUrl`` is "" for same-origin or "http://localhost:PORT" for
  // cross-origin dev; preserve the same join semantics the websocket
  // hydration helper uses.
  const base = apiBaseUrl.replace(/\/+$/, "");
  return `${base}/api/runtime/warnings/blocking`;
}

/**
 * Fetch the snapshot endpoint + fold it into the store on mount.
 *
 * Returns no value — consumers read the store state via selectors.
 * Failures land in :class:`ClientMetrics` (``snapshotHydrationFailures``)
 * + the store's error slot.
 */
export function useBlockingWarningHydration(
  options: BlockingWarningHydrationOptions = {},
): void {
  const { enabled = true, fetcher = typeof fetch === "function" ? fetch : undefined } = options;
  const config = useRuntimeConfig();
  const clientMetrics = useClientMetrics();
  const hydrateSnapshot = useBlockingWarningStore((s) => s.hydrateSnapshot);
  const markLoading = useBlockingWarningStore((s) => s.markLoading);
  const markError = useBlockingWarningStore((s) => s.markError);

  useEffect(() => {
    if (!enabled) return undefined;
    if (fetcher === undefined) {
      markError("fetch is not available in this environment");
      return undefined;
    }
    const controller = new AbortController();
    const panelMetrics = getBlockingWarningPanelMetrics();
    markLoading();
    const url = blockingWarningSnapshotUrl(config.apiBaseUrl);
    (async () => {
      try {
        const response = await fetcher(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} ${response.statusText}`);
        }
        const payload = (await response.json()) as BlockingWarningEmitterSnapshot;
        hydrateSnapshot(payload);
        clientMetrics.recordSnapshotHydration();
        panelMetrics.recordHydration();
        recordBlockingWarningTrace({
          kind: "snapshot-fetched",
          detail: `groups=${payload.active_groups.length + payload.recent_groups.length}`,
        });
      } catch (cause) {
        if (controller.signal.aborted) return;
        const message = cause instanceof Error ? cause.message : String(cause);
        markError(message);
        clientMetrics.recordSnapshotHydrationFailure();
        panelMetrics.recordHydrationFailure();
        recordBlockingWarningTrace({
          kind: "snapshot-failed",
          detail: message,
        });
      }
    })();
    return () => controller.abort();
  }, [
    enabled,
    fetcher,
    config.apiBaseUrl,
    hydrateSnapshot,
    markLoading,
    markError,
    clientMetrics,
  ]);
}
