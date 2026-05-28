/**
 * Replay page — composes the canonical timeline controls.
 *
 * Uses :class:`WebSocketReplayEngineBridge` so the recording's
 * session window and playback snapshot hydrate from the dashboard's
 * existing ``/ws`` stream. The backend emits ``replay_status``
 * envelopes from ``ReplayStatusBroadcaster`` whenever the
 * ``asyncviz replay`` launcher is the live runtime; outside of
 * replay mode the bridge stays at its empty defaults and the SPA
 * renders its existing "no recording loaded" state.
 */

import { useEffect, useMemo, type JSX } from "react";
import { useWebSocketClient } from "@/app/providers/RuntimeProvider";
import {
  ReplayTimelineControls,
} from "@/dashboard/replay";
import { WebSocketReplayEngineBridge } from "@/dashboard/replay/hooks/WebSocketReplayEngineBridge";

export function ReplayPage(): JSX.Element {
  const client = useWebSocketClient();
  // One bridge per page mount — the bridge holds a single websocket
  // subscription and a small set of listeners, so re-creating per
  // render would silently drop the recording-loaded state.
  const bridge = useMemo(
    () => new WebSocketReplayEngineBridge({ client }),
    [client],
  );
  useEffect(
    () => () => {
      bridge.dispose();
    },
    [bridge],
  );

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-6 text-sm text-text">
      <header className="flex items-center justify-between gap-4">
        <h1 className="font-mono text-base uppercase tracking-widest text-text">
          Replay
        </h1>
        <span className="text-xs text-textMuted">
          Replay buffer inspection + scrubbing. Driven by replay_status envelopes.
        </span>
      </header>

      <ReplayTimelineControls bridge={bridge} />
    </div>
  );
}
