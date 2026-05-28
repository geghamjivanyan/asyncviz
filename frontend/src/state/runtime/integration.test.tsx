/**
 * End-to-end integration test for the realtime ingestion pipeline.
 *
 * Mounts a minimal dashboard shell with a real
 * :class:`RuntimeWebSocketClient`, an in-memory transport stub that
 * lets the test push canned envelopes into the client, and a stub
 * snapshot fetcher. Then drives the exact mixed envelope stream the
 * backend produces (heartbeat, runtime_snapshot, task runtime_event,
 * queue runtime_event, metrics_delta, warning_delta, timeline_delta)
 * and asserts every surface populates without silent drops.
 *
 * This is the regression guard for both fixes shipped in this
 * session:
 *
 *   * Fix A — auto-connect on dashboard mount (the shell calls
 *     ``client.start()`` without a manual button click).
 *   * Fix B — every runtime_event advances sequence/freshness/
 *     counters; non-task events land in the recent ring buffer +
 *     histogram instead of being silently dropped.
 */

import { afterEach, describe, expect, it } from "vitest";
import { act, render } from "@testing-library/react";
import { ConfigProvider } from "@/app/providers/ConfigProvider";
import { RuntimeProvider } from "@/app/providers/RuntimeProvider";
import { createTestConfig } from "@/app/configuration/runtimeConfig";
import { useDashboardAutoConnect } from "@/hooks/useDashboardAutoConnect";
import { useRuntimeStore } from "@/state/runtime/store";
import { RuntimeWebSocketClient } from "@/runtime/websocket";
import type {
  TransportEvent,
  TransportEventListener,
  TransportReadyState,
  WebSocketTransport,
} from "@/runtime/websocket/transport";
import type { RuntimeEnvelope, RuntimeSnapshot } from "@/types/runtime";

/**
 * In-memory transport stub.
 *
 * Tests call ``pushEnvelope`` to deliver a frame and ``simulateClose``
 * to tear down. The transport tracks its own readyState transitions so
 * the client's lifecycle ("connecting" → "replaying" → "live") fires
 * for real.
 */
class FakeTransport implements WebSocketTransport {
  public url = "ws://test/ws";
  public readyState: TransportReadyState = "idle";
  private _listener: TransportEventListener | null = null;

  setListener(listener: TransportEventListener | null): void {
    this._listener = listener;
  }

  open(): void {
    this.readyState = "open";
    this._emit({ kind: "open" });
  }

  close(): void {
    this.readyState = "closed";
    this._emit({ kind: "close", code: 1000, reason: "test", wasClean: true });
  }

  send(): void {}

  pushEnvelope(env: RuntimeEnvelope): void {
    this._emit({ kind: "message", data: JSON.stringify(env) });
  }

  private _emit(event: TransportEvent): void {
    this._listener?.(event);
  }
}

function makeSnapshot(lastSequence: number, tasks: string[]): RuntimeSnapshot {
  return {
    metadata: {
      snapshot_version: 1,
      snapshot_id: "snap-it",
      runtime_id: "rt-it",
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
      oldest_retained_sequence: 0,
      newest_retained_sequence: lastSequence,
      replay_window_hit: true,
    },
    clock: {
      runtime_id: "rt-it",
      started_at_wall_seconds: 0,
      started_at_monotonic_ns: 0,
      wall_now_seconds: 0,
      wall_now_iso: "1970-01-01T00:00:00Z",
      monotonic_now_ns: 0,
      monotonic_now_seconds: 0,
      uptime_seconds: 0,
      uptime_ns: 0,
      current_sequence: lastSequence,
    },
    state: {
      schema_version: 1,
      generated_at: 0,
      generated_at_monotonic_ns: 0,
      last_sequence: lastSequence,
      last_event_id: null,
      runtime_id: "rt-it",
      tasks: tasks.map((id) => ({
        task_id: id,
        state: "running" as const,
        created_at: 0,
        updated_at: 0,
        asyncio_task_id: null,
        coroutine_name: null,
        task_name: null,
        parent_task_id: null,
        root_task_id: id,
        depth: 0,
        ancestor_chain: [],
        child_count: 0,
        completed_at: null,
        duration_seconds: null,
        exception_type: null,
        exception_message: null,
        cancellation_origin: null,
        runtime_id: "rt-it",
        tags: {},
        metadata: {},
      })),
      task_ids_by_state: {},
      metrics: {
        total_tasks: tasks.length,
        active_tasks: tasks.length,
        completed_tasks: 0,
        cancelled_tasks: 0,
        failed_tasks: 0,
        terminal_tasks: 0,
        average_duration_seconds: null,
        cancellations_by_origin: {},
        rejected_transitions: 0,
      },
      lineage: {
        tracked_tasks: tasks.length,
        root_tasks: tasks.length,
        max_depth: 0,
        orphan_links: 0,
        cyclic_rejections: 0,
        roots: [],
      },
      projections: {},
      transitions: {},
    },
    timeline: null,
    metrics: null,
    warnings: null,
    replay: null,
    queue: null,
    hints: {},
  };
}

function ShellHarness() {
  useDashboardAutoConnect();
  return null;
}

/**
 * Build a real RuntimeWebSocketClient with a fake transport and a
 * fake snapshot fetcher, mount the shell harness, and return the
 * handles the test needs to assert the lifecycle.
 */
async function mountDashboard(initialSnapshot: RuntimeSnapshot) {
  const transport = new FakeTransport();
  const fetcher: typeof fetch = async () =>
    ({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => initialSnapshot,
    }) as unknown as Response;
  const client = new RuntimeWebSocketClient({
    transport,
    fetcher,
    apiBaseUrl: "",
    protocolVersion: "1.0",
  });
  const config = createTestConfig();
  const utils = render(
    <ConfigProvider config={config}>
      <RuntimeProvider webSocketClient={client}>
        <ShellHarness />
      </RuntimeProvider>
    </ConfigProvider>,
  );
  // Flush the awaited hydration + transport open.
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  return { client, transport, ...utils };
}

afterEach(() => {
  useRuntimeStore.getState().reset();
});

describe("realtime ingestion — end-to-end", () => {
  it("auto-connects, hydrates, and populates every surface", async () => {
    const snapshot = makeSnapshot(10, ["t1", "t2"]);
    const { transport } = await mountDashboard(snapshot);

    // 1. After mount, hydration succeeded and the transport opened —
    //    the connection phase must be past "idle".
    let state = useRuntimeStore.getState();
    expect(state.connection.phase).not.toBe("idle");
    expect(state.connection.state).toBe("open");
    expect(Object.keys(state.tasksById)).toHaveLength(2);
    expect(state.runtime.runtimeId).toBe("rt-it");

    // 2. Inject a mixed envelope stream the way the backend bridge
    //    actually serializes events. Sequences continue from the
    //    snapshot's last_sequence.
    await act(async () => {
      transport.pushEnvelope({
        protocol_version: "1.0",
        type: "heartbeat",
        timestamp: 0,
        sequence: null,
        payload: { server_uptime_seconds: 1, connected_clients: 1 },
      });
      transport.pushEnvelope({
        protocol_version: "1.0",
        type: "runtime_event",
        timestamp: 0,
        sequence: 11,
        payload: {
          event_type: "asyncio.queue.put",
          queue_id: "q-1",
          task_id: "t1",
        } as Record<string, unknown>,
      });
      transport.pushEnvelope({
        protocol_version: "1.0",
        type: "runtime_event",
        timestamp: 0,
        sequence: 12,
        payload: {
          event_type: "asyncio.queue.metrics.updated",
          queue_id: "q-1",
        } as Record<string, unknown>,
      });
      transport.pushEnvelope({
        protocol_version: "1.0",
        type: "runtime_event",
        timestamp: 0,
        sequence: 13,
        payload: {
          event_type: "asyncio.task.completed",
          event_id: "evt-13",
          timestamp: 0,
          monotonic_ns: 0,
          runtime_id: "rt-it",
          task_id: "t1",
          task_name: null,
          coroutine_name: null,
          parent_task_id: null,
          duration_seconds: 0.5,
          metadata: {},
        } as Record<string, unknown>,
      });
      transport.pushEnvelope({
        protocol_version: "1.0",
        type: "runtime_event",
        timestamp: 0,
        sequence: 14,
        payload: {
          event_type: "asyncio.gather.completed",
          gather_id: "g-1",
        } as Record<string, unknown>,
      });
      transport.pushEnvelope({
        protocol_version: "1.0",
        type: "metrics_delta",
        timestamp: 0,
        sequence: 15,
        payload: { changes: { events_emitted: 5 } } as Record<string, unknown>,
      });
      transport.pushEnvelope({
        protocol_version: "1.0",
        type: "warning_delta",
        timestamp: 0,
        sequence: 16,
        payload: {
          change: "activated",
          sequence: 16,
          last_sequence: 16,
          warning: {
            warning_id: "w-1",
            warning_key: "block-1",
            warning_type: "blocking",
            severity: "critical",
            detector: "blocking",
            message: "blocked",
            created_sequence: 16,
            created_monotonic_ns: 0,
            created_at_wall: 0,
            last_observed_sequence: 16,
            last_observed_monotonic_ns: 0,
            last_observed_wall: 0,
            occurrence_count: 1,
            resolved: false,
            resolved_sequence: null,
            resolved_monotonic_ns: null,
            resolved_at_wall: null,
            expired: false,
            related_task_ids: [],
            lineage_root_id: null,
            metadata: {},
            runtime_id: "rt-it",
          },
        } as Record<string, unknown>,
      });
      transport.pushEnvelope({
        protocol_version: "1.0",
        type: "timeline_delta",
        timestamp: 0,
        sequence: 17,
        payload: {
          kind: "segment_opened",
          task_id: "t2",
          sequence: 17,
          open_segment: {
            task_id: "t2",
            state: "running",
            started_at: 0,
            started_at_monotonic_ns: 0,
          },
        } as Record<string, unknown>,
      });
      await Promise.resolve();
    });

    state = useRuntimeStore.getState();

    // 3. Every assertion the user asked for:

    // ── connection becomes live ──
    expect(state.connection.state).toBe("open");
    expect(state.connection.lastFrameAtMonotonicMs).toBeGreaterThan(0);

    // ── tasks populate ──
    expect(state.tasksById.t1?.state).toBe("completed");
    expect(state.tasksById.t2?.state).toBe("running");

    // ── queue events visible (not silently dropped) ──
    const queueCategoryCount = state.stats.runtimeEventsByCategory["asyncio.queue"] ?? 0;
    expect(queueCategoryCount).toBeGreaterThanOrEqual(2);
    const queueEventsInRing = state.recentRuntimeEvents.filter(
      (e) => e.category === "asyncio.queue",
    );
    expect(queueEventsInRing).toHaveLength(2);
    expect(queueEventsInRing.map((e) => e.eventType)).toEqual([
      "asyncio.queue.put",
      "asyncio.queue.metrics.updated",
    ]);

    // ── gather events visible ──
    expect(state.stats.runtimeEventsByCategory["asyncio.gather"]).toBe(1);

    // ── metrics_delta applied ──
    expect(state.stats.metricsDeltasApplied).toBe(1);
    expect(state.metrics.deltaCounts.events_emitted).toBe(5);

    // ── warning_delta applied ──
    expect(state.stats.warningDeltasApplied).toBe(1);
    expect(state.warnings.activeWarningIds).toContain("w-1");

    // ── timeline_delta applied ──
    expect(state.stats.timelineDeltasApplied).toBe(1);
    expect(state.timeline.activeSegmentsByTaskId.t2).toBeDefined();

    // ── no silent drops: total accepted envelopes match what we pushed ──
    // (heartbeat doesn't carry a sequence and counts as 1 applied;
    //  the four runtime_events + 3 deltas = 7 sequenced + 1 heartbeat = 8)
    expect(state.stats.envelopesApplied).toBe(8);
    expect(state.stats.duplicatesDropped).toBe(0);
    expect(state.stats.staleDropped).toBe(0);
    expect(state.stats.unhandledRuntimeEvents).toBe(0);
  });
});
