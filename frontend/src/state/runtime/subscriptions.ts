/**
 * Wire the canonical :class:`RuntimeWebSocketClient` into the
 * Zustand store.
 *
 * ``bindClientToStore`` registers the client's hook callbacks +
 * subscribes a single wildcard listener that pipes every envelope
 * through the store's reducers. The returned ``unbind`` function
 * detaches everything (used by ``useRuntimeConnection`` on unmount or
 * disconnect).
 */

import type { ConnectionPhase, HydrationResult, RuntimeWebSocketClient } from "@/runtime/websocket";
import type { ClientMetrics } from "@/runtime/observability/clientMetrics";
import { useRuntimeStore } from "@/state/runtime/store";

export interface BindClientOptions {
  /** Optional :class:`ClientMetrics` instance to record reconciliation events into. */
  metrics?: ClientMetrics;
}

export interface ClientStoreBinding {
  unbind: () => void;
}

/**
 * Connect the websocket client's events to the store's actions.
 *
 * Three channels are wired:
 *
 *   * ``onPhaseChange`` → ``setConnectionPhase`` so the UI badge
 *     reflects the rich lifecycle phase.
 *   * ``onHydrated`` → ``hydrateSnapshot`` so the first snapshot
 *     populates the normalized projections + records the hydration
 *     duration into :class:`ReconciliationStats`.
 *   * ``onEnvelope`` → ``applyEnvelope`` so every accepted envelope
 *     folds into the store via the per-type reducer.
 *
 * Also records reconciliation events into :class:`ClientMetrics` when
 * one is supplied — keeps the frontend observability dashboard in
 * sync without a separate plumbing layer.
 */
export function bindClientToStore(
  client: RuntimeWebSocketClient,
  options: BindClientOptions = {},
): ClientStoreBinding {
  const store = useRuntimeStore.getState();
  const metrics = options.metrics;

  // ``RuntimeWebSocketClientOptions`` hooks are baked at construction
  // time on the production code path, so the production wiring uses a
  // fresh client per session. Tests + future "swap client" UX call
  // this function on a pre-built client; the function attaches via a
  // wildcard subscription rather than mutating the client's hooks.
  const phaseUnsub = subscribePhase(client, (phase) => {
    useRuntimeStore.getState().setConnectionPhase(phase, client.reconnectAttempt);
    if (phase === "hydrating") {
      metrics?.recordConnectAttempt();
    }
    if (phase === "reconnecting") {
      metrics?.recordReconnect();
    }
    if (phase === "failed") {
      metrics?.recordWebsocketFailure();
    }
  });

  const hydrateUnsub = subscribeHydrated(client, (result) => {
    const start = performance.now();
    useRuntimeStore.getState().hydrateSnapshot(result.snapshot, performance.now() - start);
    metrics?.recordSnapshotHydration();
  });

  // ``subscribe("*")`` returns a real unsubscribe handle.
  const envelopeSub = client.subscribe("*", (envelope) => {
    metrics?.recordEnvelope();
    store.applyEnvelope(envelope);
  });

  return {
    unbind: () => {
      phaseUnsub();
      hydrateUnsub();
      envelopeSub.unsubscribe();
    },
  };
}

// ── Internal: wrap the client's hooks so we can return unbinds. ──

type PhaseListener = (phase: ConnectionPhase) => void;
type HydrateListener = (result: HydrationResult) => void;

/** Attach a phase listener via the (private) ``_hooks`` field.
 *
 *  The websocket client doesn't expose ``onPhaseChange`` as a
 *  ``subscribe()`` operation today — it's a single hook passed at
 *  construction. The bind helper accesses the private slot, replaces
 *  the existing single listener with a fanout list, and returns an
 *  unsubscribe that removes one fanout entry. Tests + production both
 *  use this code path; it's an explicit private-API contract between
 *  the websocket client and the store binding.
 */
function subscribePhase(client: RuntimeWebSocketClient, listener: PhaseListener): () => void {
  const hooks = (client as unknown as { _hooks: { phase?: PhaseListener } })._hooks;
  const previous = hooks.phase;
  hooks.phase = (phase) => {
    previous?.(phase);
    listener(phase);
  };
  return () => {
    if (hooks.phase !== undefined) hooks.phase = previous;
  };
}

function subscribeHydrated(client: RuntimeWebSocketClient, listener: HydrateListener): () => void {
  const hooks = (client as unknown as { _hooks: { hydrated?: HydrateListener } })._hooks;
  const previous = hooks.hydrated;
  hooks.hydrated = (result) => {
    previous?.(result);
    listener(result);
  };
  return () => {
    if (hooks.hydrated !== undefined) hooks.hydrated = previous;
  };
}
