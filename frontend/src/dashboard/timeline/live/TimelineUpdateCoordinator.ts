/**
 * Coordinator that bridges the runtime websocket / store to the
 * canonical :class:`TimelineLiveEngine`.
 *
 * The coordinator is the only piece that knows about both the
 * runtime websocket client and the canvas engine — keeping that
 * knowledge in one place means the engine itself stays
 * framework-free and the websocket client doesn't grow a render
 * dependency.
 *
 * Today the coordinator wires three channels:
 *
 *   1. ``client.subscribe("*", fn)`` — every envelope flows into
 *      ``engine.processEnvelope``;
 *   2. selector polling via the optional ``observeActiveSegments``
 *      callback — the consumer pushes the latest active count into
 *      the engine's animation clock;
 *   3. ``unbind()`` — tears down both channels.
 */

import type { RuntimeEnvelope } from "@/types/runtime";
import type { RuntimeWebSocketClient, Subscription } from "@/runtime/websocket";
import type { TimelineLiveEngine } from "@/dashboard/timeline/live/TimelineLiveEngine";

export interface UpdateCoordinatorOptions {
  engine: TimelineLiveEngine;
  client: RuntimeWebSocketClient;
}

export interface UpdateCoordinatorBinding {
  unbind: () => void;
}

export function bindLiveEngineToClient(
  options: UpdateCoordinatorOptions,
): UpdateCoordinatorBinding {
  const { engine, client } = options;
  const subscription: Subscription = client.subscribe("*", (envelope: RuntimeEnvelope) => {
    engine.processEnvelope(envelope);
  });
  return {
    unbind: () => {
      subscription.unsubscribe();
    },
  };
}
