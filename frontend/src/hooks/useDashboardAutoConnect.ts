/**
 * Dashboard-shell-level auto-connect.
 *
 * :func:`useRuntimeConnection` (and :func:`useHydrateRuntime` underneath
 * it) deliberately stay opt-in — replay-only pages, the login screen,
 * error boundaries, and the test harness must NOT open a websocket on
 * mount. The realtime dashboard, however, exists precisely to show
 * live runtime state, so it has to drive the lifecycle itself.
 *
 * This hook is the dashboard's contract with the runtime connection:
 *
 *   * On mount → call ``connect()`` exactly once.
 *   * On unmount → call ``disconnect()``.
 *
 * Both ``connect`` and ``disconnect`` returned by
 * :func:`useRuntimeConnection` are already idempotent (the underlying
 * ``useHydrateRuntime`` guards on a ``binding`` ref), so React 18
 * StrictMode's double-invoke of effects is safe: the second
 * connect() is a no-op while the first binding is alive, and the
 * cleanup→remount cycle correctly closes and reopens the socket via
 * the ``stop()``/``start()`` pair on :class:`RuntimeWebSocketClient`.
 *
 * Returns the same shape as :func:`useRuntimeConnection` so consumers
 * that want the manual Connect/Disconnect controls (e.g. the header
 * button) can read the current connection state without an extra
 * hook call.
 */

import { useEffect } from "react";
import { useRuntimeConnection } from "@/hooks/useRuntimeConnection";

export function useDashboardAutoConnect(): ReturnType<typeof useRuntimeConnection> {
  const runtime = useRuntimeConnection();
  const { connect, disconnect } = runtime;

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
    // ``connect``/``disconnect`` come from ``useCallback`` with stable
    // deps (the websocket client + client metrics are constructed once
    // in :class:`RuntimeProvider`). Including them as deps preserves
    // the lint contract without churning the effect.
  }, [connect, disconnect]);

  return runtime;
}
