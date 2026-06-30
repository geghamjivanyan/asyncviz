/**
 * Tests for :class:`WebSocketReplayEngineBridge`.
 *
 * The bridge subscribes to ``replay_status`` envelopes from a
 * canonical :class:`RuntimeWebSocketClient` and updates its own
 * window + playback snapshot. These tests pin the wire contract +
 * the listener fan-out.
 */

import { describe, expect, it, vi } from "vitest";
import type { EnvelopeListener, Subscription, SubscriptionFilter } from "@/runtime/websocket";
import type { RuntimeEnvelope } from "@/types/runtime";
import {
  WebSocketReplayEngineBridge,
  type WebSocketReplayEngineBridgeOptions,
} from "@/dashboard/replay/hooks/WebSocketReplayEngineBridge";

/** Minimal client stub matching the surface the bridge uses. */
function makeFakeClient() {
  const listeners: Array<{
    filter: SubscriptionFilter;
    listener: EnvelopeListener;
  }> = [];
  const client = {
    subscribe(filter: SubscriptionFilter, listener: EnvelopeListener): Subscription {
      const entry = { filter, listener };
      listeners.push(entry);
      return {
        unsubscribe: () => {
          const idx = listeners.indexOf(entry);
          if (idx >= 0) listeners.splice(idx, 1);
        },
      };
    },
    // The real ``RuntimeWebSocketClient`` exposes many methods we
    // don't exercise in this suite; cast to the bridge's declared
    // ``client`` field type (i.e. ``RuntimeWebSocketClient``) so the
    // bridge constructor accepts the stub while only the subset we
    // actually use is implemented. ``WebSocketReplayEngineBridgeOptions``
    // is the right anchor — it makes the test type-track the bridge's
    // public contract instead of probing class internals via
    // ``Parameters<>``/``ConstructorParameters<>``.
  } as unknown as WebSocketReplayEngineBridgeOptions["client"];
  return {
    client,
    emit(envelope: RuntimeEnvelope): void {
      for (const { filter, listener } of listeners) {
        if (filter === "replay_status" || filter === "*") listener(envelope);
      }
    },
    listenerCount: () => listeners.length,
  };
}

function statusEnvelope(payload: Record<string, unknown>): RuntimeEnvelope {
  return {
    protocol_version: "1.0",
    type: "replay_status",
    timestamp: 0,
    sequence: null,
    payload,
  };
}

describe("WebSocketReplayEngineBridge", () => {
  it("starts with the empty window + idle playback", () => {
    const { client } = makeFakeClient();
    const bridge = new WebSocketReplayEngineBridge({ client });
    expect(bridge.getSessionWindow()).toEqual({
      minSequence: 0,
      maxSequence: 0,
      minMonotonicNs: 0,
      maxMonotonicNs: 0,
    });
    expect(bridge.getPlaybackSnapshot().state).toBe("idle");
    expect(bridge.getPlaybackSnapshot().speed).toBe(1);
  });

  it("hydrates window + playback from a replay_status envelope", () => {
    const fake = makeFakeClient();
    const bridge = new WebSocketReplayEngineBridge({ client: fake.client });
    fake.emit(
      statusEnvelope({
        recording: { bundle_id: "b1", runtime_id: "rt-1", event_count: 100 },
        window: {
          min_sequence: 1,
          max_sequence: 100,
          min_monotonic_ns: 0,
          max_monotonic_ns: 5_000,
        },
        playback: {
          state: "playing",
          speed: 2,
          last_sequence: 42,
          last_monotonic_ns: 1234,
          frames_dispatched: 50,
          paused: false,
        },
      }),
    );
    expect(bridge.getSessionWindow().maxSequence).toBe(100);
    expect(bridge.getSessionWindow().minSequence).toBe(1);
    expect(bridge.getPlaybackSnapshot()).toEqual({
      state: "playing",
      speed: 2,
      lastSequence: 42,
      lastMonotonicNs: 1234,
      framesDispatched: 50,
      paused: false,
      errorDetail: undefined,
    });
  });

  it("notifies playback subscribers on every envelope", () => {
    const fake = makeFakeClient();
    const bridge = new WebSocketReplayEngineBridge({ client: fake.client });
    const observed = vi.fn();
    bridge.subscribePlayback(observed);

    fake.emit(
      statusEnvelope({
        window: { max_sequence: 50 },
        playback: { state: "playing", last_sequence: 10 },
      }),
    );
    fake.emit(
      statusEnvelope({
        window: { max_sequence: 50 },
        playback: { state: "paused", last_sequence: 25 },
      }),
    );
    expect(observed).toHaveBeenCalledTimes(2);
    expect(observed.mock.calls[1]![0].state).toBe("paused");
    expect(observed.mock.calls[1]![0].lastSequence).toBe(25);
  });

  it("treats unknown playback state strings as the previous state", () => {
    const fake = makeFakeClient();
    const bridge = new WebSocketReplayEngineBridge({ client: fake.client });
    fake.emit(
      statusEnvelope({
        playback: { state: "playing", last_sequence: 5 },
      }),
    );
    fake.emit(
      statusEnvelope({
        playback: { state: "totally-bogus-state", last_sequence: 6 },
      }),
    );
    // Unknown state ignored — "playing" carries over.
    expect(bridge.getPlaybackSnapshot().state).toBe("playing");
    expect(bridge.getPlaybackSnapshot().lastSequence).toBe(6);
  });

  it("recorded intents accumulate on dispatch (control endpoint TODO)", () => {
    const { client } = makeFakeClient();
    const bridge = new WebSocketReplayEngineBridge({ client });
    bridge.dispatch({ type: "play" });
    bridge.dispatch({ type: "set-speed", speed: 4 });
    expect(bridge.intents).toEqual([{ type: "play" }, { type: "set-speed", speed: 4 }]);
  });

  it("dispose removes the websocket subscription", () => {
    const fake = makeFakeClient();
    const bridge = new WebSocketReplayEngineBridge({ client: fake.client });
    expect(fake.listenerCount()).toBe(1);
    bridge.dispose();
    expect(fake.listenerCount()).toBe(0);
  });

  it("loaded-state contract: maxSequence > 0 after the first envelope", () => {
    // This is the exact contract the SPA's accessibility text relies
    // on: ``window.maxSequence > 0`` → "loaded"; else "no recording
    // loaded".
    const fake = makeFakeClient();
    const bridge = new WebSocketReplayEngineBridge({ client: fake.client });
    expect(bridge.getSessionWindow().maxSequence).toBe(0);
    fake.emit(
      statusEnvelope({
        window: { max_sequence: 7 },
        playback: { state: "idle" },
      }),
    );
    expect(bridge.getSessionWindow().maxSequence).toBeGreaterThan(0);
  });
});
