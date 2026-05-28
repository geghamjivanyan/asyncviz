/**
 * High-level hydration orchestrator.
 *
 * ``useHydrateRuntime`` is the React-facing entrypoint: bind the
 * canonical websocket client to the store + start the client. The
 * returned object exposes ``start`` / ``stop`` so the UI can drive
 * the lifecycle from a button or a route-level effect.
 *
 * The actual reducer wiring lives in :func:`bindClientToStore`. This
 * module is the thin glue that adapts it for React.
 */

import { useCallback, useEffect, useRef } from "react";
import { useClientMetrics, useWebSocketClient } from "@/app/providers/RuntimeProvider";
import { bindClientToStore } from "@/state/runtime/subscriptions";
import type { ClientStoreBinding } from "@/state/runtime/subscriptions";

export interface UseHydrateRuntimeResult {
  start: () => Promise<void>;
  stop: () => void;
}

/**
 * Hook that orchestrates the runtime hydration flow.
 *
 * Lifetime model:
 *
 *   * On mount the hook does nothing — the binding is created only
 *     when ``start()`` is called. This lets pages that don't need a
 *     live connection (login screen, error fallback) skip the
 *     websocket entirely.
 *   * ``start()`` binds the client to the store + calls
 *     :meth:`client.start`. Idempotent: a second call while already
 *     bound is a no-op.
 *   * ``stop()`` unbinds + closes the client cleanly. Also fires on
 *     component unmount via :func:`useEffect`'s cleanup.
 */
export function useHydrateRuntime(): UseHydrateRuntimeResult {
  const client = useWebSocketClient();
  const metrics = useClientMetrics();
  const binding = useRef<ClientStoreBinding | null>(null);

  const start = useCallback(async () => {
    if (binding.current !== null) return;
    binding.current = bindClientToStore(client, { metrics });
    await client.start();
  }, [client, metrics]);

  const stop = useCallback(() => {
    if (binding.current === null) return;
    binding.current.unbind();
    binding.current = null;
    client.stop();
  }, [client]);

  useEffect(() => () => stop(), [stop]);

  return { start, stop };
}
