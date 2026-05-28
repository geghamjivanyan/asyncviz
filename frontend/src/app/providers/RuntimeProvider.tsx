/**
 * Owns the long-lived runtime resources for the application:
 *
 *   * :class:`RuntimeWebSocketClient` — canonical replay-aware
 *     websocket client. Constructed but not auto-started here; the
 *     consumer (typically :func:`useRuntimeConnection`) calls
 *     :meth:`start` / :meth:`stop`.
 *   * :class:`ClientMetrics` — frontend observability counters.
 *
 * Components read via :func:`useWebSocketClient` and
 * :func:`useClientMetrics`. The provider does not connect the
 * websocket itself — that's the responsibility of an explicit
 * ``connect()`` / ``start()`` call. The provider exists so the same
 * instances are shared across the tree without a module-level
 * singleton.
 */

import { createContext, useContext, useMemo } from "react";
import type { ReactNode } from "react";
import { useRuntimeConfig } from "@/app/providers/ConfigProvider";
import { ClientMetrics } from "@/runtime/observability/clientMetrics";
import { NativeWebSocketTransport, RuntimeWebSocketClient } from "@/runtime/websocket";

interface RuntimeContextValue {
  webSocketClient: RuntimeWebSocketClient;
  metrics: ClientMetrics;
}

const RuntimeContext = createContext<RuntimeContextValue | null>(null);

export interface RuntimeProviderProps {
  /** Test-only override — pass a custom :class:`RuntimeWebSocketClient`. */
  webSocketClient?: RuntimeWebSocketClient;
  /** Test-only override — pass a fresh metrics instance. */
  metrics?: ClientMetrics;
  children: ReactNode;
}

export function RuntimeProvider({ webSocketClient, metrics, children }: RuntimeProviderProps) {
  const config = useRuntimeConfig();
  const value = useMemo<RuntimeContextValue>(
    () => {
      const resolvedMetrics = metrics ?? new ClientMetrics();
      const resolvedWebSocketClient =
        webSocketClient ??
        new RuntimeWebSocketClient({
          transport: new NativeWebSocketTransport(config.websocketUrl),
          apiBaseUrl: config.apiBaseUrl,
          protocolVersion: config.protocolVersion,
        });
      return {
        webSocketClient: resolvedWebSocketClient,
        metrics: resolvedMetrics,
      };
    },
    // Construction is deliberately one-shot — overrides apply when the
    // provider mounts. ``config.*`` is stable for the lifetime of the
    // app, so re-creating on URL changes is a non-goal today.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  return <RuntimeContext.Provider value={value}>{children}</RuntimeContext.Provider>;
}

export function useRuntimeContext(): RuntimeContextValue {
  const ctx = useContext(RuntimeContext);
  if (ctx === null) {
    throw new Error(
      "useRuntimeContext must be used inside a <RuntimeProvider>. Wrap your app in <AppProviders>.",
    );
  }
  return ctx;
}

export function useWebSocketClient(): RuntimeWebSocketClient {
  return useRuntimeContext().webSocketClient;
}

export function useClientMetrics(): ClientMetrics {
  return useRuntimeContext().metrics;
}
