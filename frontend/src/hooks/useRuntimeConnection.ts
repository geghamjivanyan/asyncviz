/**
 * Public hook driving the runtime websocket connection.
 *
 * Composes :func:`useHydrateRuntime` (which binds the canonical
 * :class:`RuntimeWebSocketClient` to the Zustand store + starts the
 * client) with a small UI-facing API:
 *
 *   ``connection`` — current :type:`ConnectionState` for legacy
 *   compatibility with existing UI (status badge, dot).
 *   ``connect()``  — kick off hydration + open the socket. Idempotent.
 *   ``disconnect()`` — close the socket gracefully.
 *
 * The hook intentionally does not auto-start on mount — the user
 * (or the dashboard shell) decides when to begin streaming. This
 * keeps tests + login screens + error fallbacks from creating
 * accidental connections.
 */

import { useCallback } from "react";
import { useConnectionState } from "@/state/runtime";
import { useHydrateRuntime } from "@/state/runtime";

export function useRuntimeConnection() {
  const connection = useConnectionState();
  const { start, stop } = useHydrateRuntime();

  const connect = useCallback(() => {
    void start();
  }, [start]);

  const disconnect = useCallback(() => {
    stop();
  }, [stop]);

  return { connection, connect, disconnect };
}
