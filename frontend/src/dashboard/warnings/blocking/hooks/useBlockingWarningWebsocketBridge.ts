/**
 * Websocket subscription factory for blocking-warning lifecycle events.
 *
 * Blocking-warning transitions ride on ``runtime_event`` envelopes
 * whose payload is a serialized :class:`GenericEvent`. The actual
 * wire-shape :type:`BlockingWarningEventPayload` lives at
 * ``envelope.payload.payload``. The bridge demultiplexes those
 * envelopes against the five blocking-warning event types and forwards
 * each payload into the live-update store action.
 *
 * Designed as a *factory* so :func:`useBlockingWarningLiveUpdates`
 * stays websocket-agnostic and tests can drive the same path with a
 * stub client.
 */

import { useEffect, useMemo } from "react";
import { useWebSocketClient } from "@/app/providers/RuntimeProvider";
import type { RuntimeEnvelope } from "@/types/runtime";
import type { BlockingWarningEventPayload } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import type { BlockingWarningSubscribeFactory } from "@/dashboard/warnings/blocking/hooks/useBlockingWarningLiveUpdates";
import { useBlockingWarningLiveUpdates } from "@/dashboard/warnings/blocking/hooks/useBlockingWarningLiveUpdates";
import { BLOCKING_WARNING_EVENT_TYPES } from "@/dashboard/warnings/blocking/BlockingWarningStore";

/** A minimal slice of the websocket client this hook actually uses. */
export interface BlockingWarningEnvelopeSource {
  subscribe(
    filter: "runtime_event",
    listener: (envelope: RuntimeEnvelope) => void,
  ): { unsubscribe: () => void };
}

const BLOCKING_EVENT_TYPE_SET: ReadonlySet<string> = new Set(BLOCKING_WARNING_EVENT_TYPES);

/**
 * Coerce a ``runtime_event`` envelope into a blocking-warning payload.
 *
 * Returns ``null`` for any envelope whose ``event_type`` isn't one of
 * the five lifecycle wire types — keeps the hot path branch-free in
 * the common case where blocking events are a tiny fraction of all
 * runtime events.
 */
export function blockingPayloadFromEnvelope(
  envelope: RuntimeEnvelope,
): BlockingWarningEventPayload | null {
  const outer = envelope.payload as
    { event_type?: string; payload?: BlockingWarningEventPayload } | undefined;
  if (outer === undefined) return null;
  const eventType = outer.event_type;
  if (typeof eventType !== "string") return null;
  if (!BLOCKING_EVENT_TYPE_SET.has(eventType)) return null;
  const inner = outer.payload;
  if (inner === undefined || inner === null) return null;
  return inner;
}

/**
 * Build a :type:`BlockingWarningSubscribeFactory` for a given source.
 *
 * The factory registers a single ``runtime_event`` subscription on the
 * source and forwards filtered payloads to the panel's apply callback.
 * Exposed standalone so tests can stub the source without touching
 * React.
 */
export function makeBlockingWarningSubscribeFactory(
  source: BlockingWarningEnvelopeSource,
): BlockingWarningSubscribeFactory {
  return (apply) => {
    const sub = source.subscribe("runtime_event", (envelope) => {
      const payload = blockingPayloadFromEnvelope(envelope);
      if (payload !== null) apply(payload);
    });
    return () => sub.unsubscribe();
  };
}

export interface UseBlockingWarningWebsocketBridgeOptions {
  /** When ``false``, the bridge skips the websocket subscription. */
  enabled?: boolean;
}

/**
 * Hook variant — wires the live-update hook to the runtime websocket
 * client from :func:`useWebSocketClient`. Components that just want
 * live updates from the canonical websocket call this; the underlying
 * :func:`useBlockingWarningLiveUpdates` is still available for tests
 * that want to inject a stub.
 *
 * ``enabled`` is honored as a *factory* gate so the rules of hooks
 * stay intact — the hook itself runs every render; only the inner
 * subscription is skipped when disabled.
 */
export function useBlockingWarningWebsocketBridge(
  options: UseBlockingWarningWebsocketBridgeOptions = {},
): void {
  const { enabled = true } = options;
  const client = useWebSocketClient();
  const subscribe = useMemo<BlockingWarningSubscribeFactory | undefined>(
    () => (enabled ? makeBlockingWarningSubscribeFactory(client) : undefined),
    [enabled, client],
  );
  useBlockingWarningLiveUpdates({ subscribe });

  // The live-updates hook owns the registration lifecycle; this effect
  // exists purely to give the bridge a deterministic mount/unmount
  // log line — useful when chasing reconciliation bugs in DevTools.
  useEffect(() => {
    return () => {
      // no-op cleanup; subscription is owned by the inner hook.
    };
  }, []);
}
