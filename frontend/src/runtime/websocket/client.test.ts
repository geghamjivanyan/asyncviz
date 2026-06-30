/**
 * Integration tests for :class:`RuntimeWebSocketClient`.
 *
 * Uses a fake transport so the full client flow (hydrate → connect →
 * receive frames → disconnect → reconnect) can run deterministically
 * under JSDOM.
 */

import { describe, expect, it, vi } from "vitest";
import { RuntimeWebSocketClient } from "@/runtime/websocket/client";
import type {
  TransportEvent,
  TransportEventListener,
  TransportReadyState,
  WebSocketTransport,
} from "@/runtime/websocket/transport";

class FakeTransport implements WebSocketTransport {
  url: string;
  readyState: TransportReadyState = "idle";
  opens = 0;
  closes = 0;
  setUrl(url: string) {
    this.url = url;
  }
  private listener: TransportEventListener | null = null;

  constructor(url: string) {
    this.url = url;
  }

  setListener(listener: TransportEventListener | null): void {
    this.listener = listener;
  }

  open(): void {
    this.opens += 1;
    this.readyState = "open";
    this.listener?.({ kind: "open" });
  }

  close(_code?: number, _reason?: string): void {
    if (this.readyState === "closed") return;
    this.readyState = "closed";
    this.closes += 1;
    this.listener?.({
      kind: "close",
      code: _code ?? 1000,
      reason: _reason ?? "",
      wasClean: true,
    });
  }

  send(_payload: string): void {
    // not exercised
  }

  /** Test helper — push a frame through the listener. */
  emit(event: TransportEvent): void {
    this.listener?.(event);
  }

  /** Test helper — push a JSON envelope through as a message. */
  emitEnvelope(env: Record<string, unknown>): void {
    this.listener?.({ kind: "message", data: JSON.stringify(env) });
  }
}

function snapshotResponse(lastSequence: number, runtimeId: string = "test-runtime") {
  return {
    metadata: {
      snapshot_version: 1,
      snapshot_id: "snap-1",
      runtime_id: runtimeId,
      generated_at: 0,
      generated_at_monotonic_ns: 0,
      generation_duration_ns: 0,
      payload_bytes: 0,
      is_full: true,
      included_sources: [],
      skipped_sources: [],
    },
    consistency: {
      last_sequence: lastSequence,
      last_event_id: null,
      generated_at_monotonic_ns: 0,
      generated_at: 0,
      oldest_retained_sequence: null,
      newest_retained_sequence: null,
      replay_window_hit: true,
    },
    clock: {},
    state: null,
    timeline: null,
    metrics: null,
    warnings: null,
    replay: null,
    queue: null,
    hints: {},
  };
}

function fakeFetch(payload: object): typeof fetch {
  return (async () =>
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    })) as unknown as typeof fetch;
}

function buildClient(
  overrides: Partial<ConstructorParameters<typeof RuntimeWebSocketClient>[0]> = {},
) {
  const transport = new FakeTransport("ws://test/ws");
  const client = new RuntimeWebSocketClient({
    transport,
    apiBaseUrl: "http://test",
    protocolVersion: "1.0",
    fetcher: fakeFetch(snapshotResponse(5)),
    reconnect: { baseDelayMs: 10, jitter: 0, random: () => 0 },
    heartbeat: { staleThresholdMs: 1_000_000 },
    setTimer: (cb, ms) => setTimeout(cb, ms),
    clearTimer: (id) => clearTimeout(id as ReturnType<typeof setTimeout>),
    ...overrides,
  });
  return { client, transport };
}

describe("RuntimeWebSocketClient — happy path", () => {
  it("hydrates, opens the transport, then transitions to live on first envelope", async () => {
    const { client, transport } = buildClient();
    const phases: string[] = [];
    client.diagnostics.setEnabled(true);
    const original = (client as unknown as { _hooks: { phase: (p: string) => void } })._hooks;
    original.phase = (p) => phases.push(p);
    await client.start();
    expect(transport.opens).toBe(1);
    expect(client.lastSequence).toBe(5);
    expect(client.phase).toBe("replaying");
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: { event_type: "asyncio.task.created", task_id: "t1" },
      sequence: 6,
    });
    expect(client.phase).toBe("live");
    expect(client.lastSequence).toBe(6);
    expect(phases).toContain("hydrating");
    expect(phases).toContain("connecting");
    expect(phases).toContain("replaying");
    expect(phases).toContain("live");
  });

  it("delivers envelopes to typed subscribers", async () => {
    const { client, transport } = buildClient();
    const metricsListener = vi.fn();
    const warningListener = vi.fn();
    client.subscribe("metrics_delta", metricsListener);
    client.subscribe("warning_delta", warningListener);
    await client.start();
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "metrics_delta",
      payload: {},
      sequence: 6,
    });
    expect(metricsListener).toHaveBeenCalledTimes(1);
    expect(warningListener).not.toHaveBeenCalled();
  });
});

describe("RuntimeWebSocketClient — sequencing", () => {
  it("drops duplicate frames", async () => {
    const { client, transport } = buildClient();
    const rejects: string[] = [];
    const onEnvelope = vi.fn();
    const rebuilt = new RuntimeWebSocketClient({
      transport,
      apiBaseUrl: "http://test",
      protocolVersion: "1.0",
      fetcher: fakeFetch(snapshotResponse(5)),
      reconnect: { baseDelayMs: 10, jitter: 0, random: () => 0 },
      heartbeat: { staleThresholdMs: 1_000_000 },
      onEnvelope,
      onReject: (reason) => rejects.push(reason),
    });
    await rebuilt.start();
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: {},
      sequence: 6,
    });
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: {},
      sequence: 6,
    });
    expect(onEnvelope).toHaveBeenCalledTimes(1);
    expect(rejects).toContain("duplicate");
    // Suppress unused-binding warning on ``client``.
    void client;
  });

  it("drops stale frames behind the cursor", async () => {
    const rejects: string[] = [];
    const transport = new FakeTransport("ws://test/ws");
    const client = new RuntimeWebSocketClient({
      transport,
      apiBaseUrl: "http://test",
      protocolVersion: "1.0",
      fetcher: fakeFetch(snapshotResponse(10)),
      reconnect: { baseDelayMs: 10, jitter: 0, random: () => 0 },
      heartbeat: { staleThresholdMs: 1_000_000 },
      onReject: (reason) => rejects.push(reason),
    });
    await client.start();
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: {},
      sequence: 5,
    });
    expect(rejects).toContain("stale");
  });

  it("treats runtime_snapshot envelopes as a cursor resnap", async () => {
    const transport = new FakeTransport("ws://test/ws");
    const client = new RuntimeWebSocketClient({
      transport,
      apiBaseUrl: "http://test",
      protocolVersion: "1.0",
      fetcher: fakeFetch(snapshotResponse(10)),
      reconnect: { baseDelayMs: 10, jitter: 0, random: () => 0 },
      heartbeat: { staleThresholdMs: 1_000_000 },
    });
    await client.start();
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_snapshot",
      payload: { last_sequence: 42, tasks: [] },
      sequence: null,
    });
    expect(client.lastSequence).toBe(42);
    expect(client.phase).toBe("live");
  });
});

describe("RuntimeWebSocketClient — reconnect", () => {
  it("schedules a reconnect when the transport closes unexpectedly", async () => {
    const { client, transport } = buildClient({
      reconnect: { baseDelayMs: 1, jitter: 0, random: () => 0 },
    });
    await client.start();
    expect(transport.opens).toBe(1);
    transport.close();
    expect(client.phase).toBe("reconnecting");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(transport.opens).toBeGreaterThanOrEqual(2);
  });

  it("stops trying when stop() is called mid-reconnect", async () => {
    const { client, transport } = buildClient({
      reconnect: { baseDelayMs: 50, jitter: 0, random: () => 0 },
    });
    await client.start();
    transport.close();
    client.stop();
    expect(client.phase).toBe("disconnected");
    await new Promise((resolve) => setTimeout(resolve, 100));
    // Transport stayed at 1 open after the initial connect.
    expect(transport.opens).toBe(1);
  });

  it("rejects malformed JSON via the onReject hook", async () => {
    const rejects: string[] = [];
    const transport = new FakeTransport("ws://test/ws");
    const client = new RuntimeWebSocketClient({
      transport,
      apiBaseUrl: "http://test",
      protocolVersion: "1.0",
      fetcher: fakeFetch(snapshotResponse(0)),
      reconnect: { baseDelayMs: 10, jitter: 0, random: () => 0 },
      heartbeat: { staleThresholdMs: 1_000_000 },
      onReject: (reason) => rejects.push(reason),
    });
    await client.start();
    transport.emit({ kind: "message", data: "{ broken" });
    expect(rejects).toContain("invalid-json");
  });
});

describe("RuntimeWebSocketClient — hydration", () => {
  it("falls back to direct connect when snapshot fetch fails", async () => {
    const transport = new FakeTransport("ws://test/ws");
    const client = new RuntimeWebSocketClient({
      transport,
      apiBaseUrl: "http://test",
      protocolVersion: "1.0",
      fetcher: (async () => {
        throw new Error("offline");
      }) as unknown as typeof fetch,
      reconnect: { baseDelayMs: 10, jitter: 0, random: () => 0 },
      heartbeat: { staleThresholdMs: 1_000_000 },
    });
    const errors: unknown[] = [];
    await new RuntimeWebSocketClient({
      transport,
      apiBaseUrl: "http://test",
      protocolVersion: "1.0",
      fetcher: (async () => {
        throw new Error("offline");
      }) as unknown as typeof fetch,
      reconnect: { baseDelayMs: 10, jitter: 0, random: () => 0 },
      heartbeat: { staleThresholdMs: 1_000_000 },
      onError: (e) => errors.push(e),
    }).start();
    await client.start();
    // Fallback path: lastSequence reset to 0 + transport opened anyway.
    expect(client.lastSequence).toBe(0);
    expect(transport.opens).toBeGreaterThanOrEqual(1);
    expect(errors).not.toHaveLength(0);
  });
});

/**
 * Regression tests for the stuck-CONNECTING bug.
 *
 * Before the fix, ``_handleMessage`` flipped phase to ``live`` only
 * when the current phase was ``replaying``. If the transport's
 * ``open`` event was missed (e.g. listener attached after the
 * native ``WebSocket`` already opened, or the order of open vs
 * first-message was inverted under load), the phase stuck at
 * ``connecting`` forever — even though envelopes kept arriving and
 * the EVENTS counter kept incrementing.
 *
 * These tests reach into ``_phase`` via the documented test seam
 * (cast to ``{ _phase: ConnectionPhase }``) to simulate the missed
 * transition, then assert that the next envelope drives the
 * connection state to ``live``.
 */
describe("RuntimeWebSocketClient — phase recovery", () => {
  function forcePhase(
    client: RuntimeWebSocketClient,
    phase:
      | "idle"
      | "hydrating"
      | "connecting"
      | "replaying"
      | "live"
      | "reconnecting"
      | "disconnected"
      | "failed",
  ): void {
    (client as unknown as { _phase: string })._phase = phase;
  }

  it("flips out of connecting when a message arrives (open event was missed)", async () => {
    const { client, transport } = buildClient();
    await client.start();
    // Force the phase back to "connecting" — mimics the race where
    // the open event never reached the listener.
    forcePhase(client, "connecting");
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: { event_type: "asyncio.task.created", task_id: "t1" },
      sequence: 6,
    });
    expect(client.phase).toBe("live");
  });

  it("flips out of hydrating when a message arrives", async () => {
    const { client, transport } = buildClient();
    await client.start();
    forcePhase(client, "hydrating");
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "metrics_delta",
      payload: { changes: {} },
      sequence: 6,
    });
    expect(client.phase).toBe("live");
  });

  it("flips out of reconnecting when a message arrives mid-reconnect", async () => {
    const { client, transport } = buildClient();
    await client.start();
    forcePhase(client, "reconnecting");
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "warning_delta",
      payload: { change: "activated", sequence: 6, last_sequence: 6, warning: null },
      sequence: 6,
    });
    expect(client.phase).toBe("live");
  });

  it("keeps phase=live on subsequent envelopes (no spurious transitions)", async () => {
    const { client, transport } = buildClient();
    await client.start();
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: { event_type: "asyncio.task.created", task_id: "t1" },
      sequence: 6,
    });
    expect(client.phase).toBe("live");
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: { event_type: "asyncio.task.completed", task_id: "t1" },
      sequence: 7,
    });
    expect(client.phase).toBe("live");
  });

  it("does NOT silently revive disconnected after stop()", async () => {
    const { client, transport } = buildClient();
    await client.start();
    client.stop();
    expect(client.phase).toBe("disconnected");
    // A stray late frame after stop must not flip the connection
    // state back to live — the transport is closed; a "live" badge
    // would be a lie.
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: { event_type: "asyncio.task.created", task_id: "t2" },
      sequence: 7,
    });
    expect(client.phase).toBe("disconnected");
  });

  it("does NOT revive failed phase from a late frame", async () => {
    const { client, transport } = buildClient();
    await client.start();
    forcePhase(client, "failed");
    transport.emitEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      payload: { event_type: "asyncio.task.created", task_id: "t3" },
      sequence: 7,
    });
    expect(client.phase).toBe("failed");
  });
});
