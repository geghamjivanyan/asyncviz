/**
 * Tests for the pure store → connection-summary projection.
 *
 * Operates on synthetic inputs — no React, no Zustand. The
 * projection's responsibility is to be deterministic and replay-safe.
 */

import { describe, expect, it } from "vitest";
import {
  projectConnection,
  projectHeartbeat,
  projectHydration,
  projectPhase,
  projectReconnect,
  projectReplaySync,
  type ConnectionProjectionInputs,
} from "@/dashboard/connection/selectors/projectConnection";
import {
  FLAKY_RECONNECT_THRESHOLD,
  HEARTBEAT_OFFLINE_MS,
  HEARTBEAT_STALE_MS,
} from "@/dashboard/connection/models/state";
import { INITIAL_RECONCILIATION_STATS, INITIAL_RUNTIME_META } from "@/state/runtime/models";

function makeInputs(
  overrides: Partial<ConnectionProjectionInputs> = {},
): ConnectionProjectionInputs {
  return {
    connection: {
      phase: "live",
      state: "open",
      reconnectAttempts: 0,
      lastFrameAtMonotonicMs: 0,
    },
    runtime: {
      ...INITIAL_RUNTIME_META,
      runtimeId: "rt-1",
      status: "running",
      serverUptimeSeconds: 100,
      connectedClients: 2,
      clock: {
        runtime_id: "rt-1",
        started_at_wall_seconds: 0,
        started_at_monotonic_ns: 0,
        wall_now_seconds: 100,
        wall_now_iso: "1970-01-01T00:01:40Z",
        monotonic_now_ns: 0,
        monotonic_now_seconds: 100,
        uptime_seconds: 100,
        uptime_ns: 0,
        current_sequence: 200,
      },
    },
    replay: {
      oldestRetainedSequence: 0,
      newestRetainedSequence: 200,
      windowHit: true,
    },
    stats: {
      ...INITIAL_RECONCILIATION_STATS,
      envelopesApplied: 50,
      hydrations: 1,
      lastHydrationDurationMs: 42,
    },
    lastSequence: 150,
    nowMs: 1000,
    hydrationInFlight: false,
    ...overrides,
  };
}

describe("projectPhase", () => {
  it("returns live + healthy visibility when the phase is live", () => {
    const phase = projectPhase(makeInputs());
    expect(phase.phase).toBe("live");
    expect(phase.visibility).toBe("live");
    expect(phase.isLive).toBe(true);
    expect(phase.label).toBe("Live");
  });

  it("flags reconnecting visibility as transitional", () => {
    const phase = projectPhase(
      makeInputs({
        connection: {
          phase: "reconnecting",
          state: "connecting",
          reconnectAttempts: 2,
          lastFrameAtMonotonicMs: 0,
        },
      }),
    );
    expect(phase.isReconnecting).toBe(true);
    expect(phase.visibility).toBe("transitional");
  });

  it("marks failed phase as error", () => {
    const phase = projectPhase(
      makeInputs({
        connection: {
          phase: "failed",
          state: "error",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 0,
        },
      }),
    );
    expect(phase.hasError).toBe(true);
    expect(phase.visibility).toBe("error");
  });

  it("derives hydrating flag from injected hydrationInFlight", () => {
    const phase = projectPhase(
      makeInputs({
        connection: {
          phase: "live",
          state: "open",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 0,
        },
        hydrationInFlight: true,
      }),
    );
    expect(phase.isHydrating).toBe(true);
  });
});

describe("projectReconnect", () => {
  it("flags flakiness at the threshold", () => {
    const r = projectReconnect(
      makeInputs({
        connection: {
          phase: "live",
          state: "open",
          reconnectAttempts: FLAKY_RECONNECT_THRESHOLD,
          lastFrameAtMonotonicMs: 0,
        },
      }),
    );
    expect(r.isFlaky).toBe(true);
  });

  it("does not flag flakiness below the threshold", () => {
    const r = projectReconnect(
      makeInputs({
        connection: {
          phase: "live",
          state: "open",
          reconnectAttempts: 1,
          lastFrameAtMonotonicMs: 0,
        },
      }),
    );
    expect(r.isFlaky).toBe(false);
  });
});

describe("projectHeartbeat", () => {
  it("derives lag from nowMs - lastFrame", () => {
    const h = projectHeartbeat(
      makeInputs({
        connection: {
          phase: "live",
          state: "open",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 500,
        },
        nowMs: 1500,
      }),
    );
    expect(h.lastFrameAgoMs).toBe(1000);
    expect(h.isStale).toBe(false);
    expect(h.isOffline).toBe(false);
  });

  it("flags stale at the freshness budget", () => {
    const h = projectHeartbeat(
      makeInputs({
        connection: {
          phase: "live",
          state: "open",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 1,
        },
        nowMs: HEARTBEAT_STALE_MS + 1,
      }),
    );
    expect(h.isStale).toBe(true);
  });

  it("flags offline at the offline budget", () => {
    const h = projectHeartbeat(
      makeInputs({
        connection: {
          phase: "live",
          state: "open",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 1,
        },
        nowMs: HEARTBEAT_OFFLINE_MS + 1,
      }),
    );
    expect(h.isOffline).toBe(true);
  });

  it("returns null lag when no frame has been seen", () => {
    const h = projectHeartbeat(makeInputs());
    expect(h.lastFrameAgoMs).toBeNull();
    expect(h.isStale).toBe(false);
    expect(h.isOffline).toBe(false);
  });
});

describe("projectHydration", () => {
  it("exposes the hydration counters", () => {
    const h = projectHydration(
      makeInputs({
        stats: {
          ...INITIAL_RECONCILIATION_STATS,
          hydrations: 4,
          lastHydrationDurationMs: 12.5,
        },
        hydrationInFlight: true,
      }),
    );
    expect(h.hydrations).toBe(4);
    expect(h.lastDurationMs).toBeCloseTo(12.5);
    expect(h.inFlight).toBe(true);
  });
});

describe("projectReplaySync", () => {
  it("computes cursorProgress from lastSequence / newest", () => {
    const r = projectReplaySync(
      makeInputs({
        lastSequence: 50,
        replay: { oldestRetainedSequence: 0, newestRetainedSequence: 100, windowHit: true },
      }),
    );
    expect(r.cursorProgress).toBeCloseTo(0.5);
  });

  it("clamps cursorProgress to 1 when last > newest", () => {
    const r = projectReplaySync(
      makeInputs({
        lastSequence: 200,
        replay: { oldestRetainedSequence: 0, newestRetainedSequence: 100, windowHit: true },
      }),
    );
    expect(r.cursorProgress).toBe(1);
  });

  it("flags windowMissed when windowHit is false", () => {
    const r = projectReplaySync(
      makeInputs({
        replay: { oldestRetainedSequence: null, newestRetainedSequence: null, windowHit: false },
      }),
    );
    expect(r.windowMissed).toBe(true);
  });
});

describe("projectConnection", () => {
  it("produces a stable signature for identical inputs", () => {
    const inputs = makeInputs();
    expect(projectConnection(inputs).signature).toEqual(projectConnection(inputs).signature);
  });

  it("changes signature when the phase changes", () => {
    const a = projectConnection(makeInputs());
    const b = projectConnection(
      makeInputs({
        connection: {
          phase: "reconnecting",
          state: "connecting",
          reconnectAttempts: 1,
          lastFrameAtMonotonicMs: 0,
        },
      }),
    );
    expect(a.signature).not.toEqual(b.signature);
  });

  it("buckets heartbeat lag so sub-quantum ticks do not invalidate the signature", () => {
    const a = projectConnection(
      makeInputs({
        connection: {
          phase: "live",
          state: "open",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 0,
        },
        nowMs: 50,
      }),
    );
    const b = projectConnection(
      makeInputs({
        connection: {
          phase: "live",
          state: "open",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 0,
        },
        nowMs: 100,
      }),
    );
    // Both samples fall in the 0–250ms bucket.
    expect(a.signature).toEqual(b.signature);
  });

  it("composes every sub-projection", () => {
    const summary = projectConnection(makeInputs());
    expect(summary.phase).toBeDefined();
    expect(summary.reconnect).toBeDefined();
    expect(summary.heartbeat).toBeDefined();
    expect(summary.hydration).toBeDefined();
    expect(summary.replay).toBeDefined();
    expect(summary.runtimeStatus).toBe("running");
  });
});

/**
 * The connection header has to differentiate LIVE runtime mode from
 * REPLAY mode — and inside replay mode, surface PAUSED / STOPPED so
 * the operator can tell at a glance whether playback is moving.
 * Driven by ``runtime.replayActive`` + ``runtime.replayPlaybackState``
 * which the store populates from ``replay_status`` envelopes.
 */
describe("projectPhase — replay-mode labels", () => {
  it("labels a live phase in replay mode as Replay (not Live)", () => {
    const phase = projectPhase(
      makeInputs({
        runtime: {
          ...INITIAL_RUNTIME_META,
          runtimeId: "rt-replay",
          status: "running",
          replayActive: true,
          replayPlaybackState: "playing",
        },
      }),
    );
    expect(phase.label).toBe("Replay");
    expect(phase.isReplaying).toBe(true);
  });

  it("labels paused replay playback as Paused", () => {
    const phase = projectPhase(
      makeInputs({
        runtime: {
          ...INITIAL_RUNTIME_META,
          replayActive: true,
          replayPlaybackState: "paused",
        },
      }),
    );
    expect(phase.label).toBe("Paused");
  });

  it("labels stopped replay playback as Stopped", () => {
    const phase = projectPhase(
      makeInputs({
        runtime: {
          ...INITIAL_RUNTIME_META,
          replayActive: true,
          replayPlaybackState: "stopped",
        },
      }),
    );
    expect(phase.label).toBe("Stopped");
  });

  it("falls back to Replay when replay is mid-seek / buffering", () => {
    const seeking = projectPhase(
      makeInputs({
        runtime: {
          ...INITIAL_RUNTIME_META,
          replayActive: true,
          replayPlaybackState: "seeking",
        },
      }),
    );
    expect(seeking.label).toBe("Seeking");
    const buffering = projectPhase(
      makeInputs({
        runtime: {
          ...INITIAL_RUNTIME_META,
          replayActive: true,
          replayPlaybackState: "buffering",
        },
      }),
    );
    expect(buffering.label).toBe("Buffering");
  });

  it("keeps the live-mode label when replayActive is false", () => {
    // Live runtime mode — the default the store starts in.
    const phase = projectPhase(makeInputs());
    expect(phase.label).toBe("Live");
    expect(phase.isReplaying).toBe(false);
  });

  it("uses the connecting label even in replay mode when phase < live", () => {
    // Before the websocket finishes connecting + handshakes, the
    // operator should see the connection state, not the replay
    // state. Otherwise a slow handshake would falsely advertise
    // "Replay" while no data has actually flowed.
    const phase = projectPhase(
      makeInputs({
        connection: {
          phase: "connecting",
          state: "connecting",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 0,
        },
        runtime: {
          ...INITIAL_RUNTIME_META,
          replayActive: true,
          replayPlaybackState: "playing",
        },
      }),
    );
    expect(phase.label).toBe("Connecting");
  });
});
