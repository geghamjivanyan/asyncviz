/**
 * Integration tests for the canonical Zustand runtime store.
 *
 * Tests reset the store between cases via :meth:`reset` to avoid
 * cross-pollution; the global ``useRuntimeStore`` is shared across the
 * test file, which is fine because each test asserts on its own
 * post-reset state.
 */

import { beforeEach, describe, expect, it } from "vitest";
import { useRuntimeStore } from "@/state/runtime/store";
import type { RuntimeEnvelope, RuntimeSnapshot, TaskLifecycleEvent } from "@/types/runtime";

function snapshotResponse(
  lastSequence: number,
  options: { tasks?: number; warningIds?: string[] } = {},
): RuntimeSnapshot {
  const { tasks = 0, warningIds = [] } = options;
  return {
    metadata: {
      snapshot_version: 1,
      snapshot_id: "snap-1",
      runtime_id: "runtime-1",
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
      runtime_id: "runtime-1",
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
      runtime_id: "runtime-1",
      tasks: Array.from({ length: tasks }, (_, i) => ({
        task_id: `t${i}`,
        state: "running" as const,
        created_at: 0,
        updated_at: 0,
        asyncio_task_id: null,
        coroutine_name: null,
        task_name: null,
        parent_task_id: null,
        root_task_id: `t${i}`,
        depth: 0,
        ancestor_chain: [],
        child_count: 0,
        completed_at: null,
        duration_seconds: null,
        exception_type: null,
        exception_message: null,
        cancellation_origin: null,
        runtime_id: "runtime-1",
        tags: {},
        metadata: {},
      })),
      task_ids_by_state: {},
      metrics: {
        total_tasks: tasks,
        active_tasks: tasks,
        completed_tasks: 0,
        cancelled_tasks: 0,
        failed_tasks: 0,
        terminal_tasks: 0,
        average_duration_seconds: null,
        cancellations_by_origin: {},
        rejected_transitions: 0,
      },
      lineage: {
        tracked_tasks: tasks,
        root_tasks: tasks,
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
    warnings:
      warningIds.length === 0
        ? null
        : {
            schema_version: 1,
            generated_at: 0,
            generated_at_monotonic_ns: 0,
            runtime_id: "runtime-1",
            last_sequence: lastSequence,
            active: warningIds.map((id) => ({
              warning_id: id,
              warning_key: id,
              warning_type: "stuck_task",
              severity: "warning",
              detector: "stuck",
              message: "stuck",
              created_sequence: null,
              created_monotonic_ns: 0,
              created_at_wall: 0,
              last_observed_sequence: null,
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
              runtime_id: null,
            })),
            resolved: [],
            counts_by_severity: { info: 0, warning: warningIds.length, error: 0, critical: 0 },
            counts_by_type: {},
            self_metrics: {
              detectors_registered: 0,
              evaluations_run: 0,
              detector_failures: 0,
              warnings_emitted: warningIds.length,
              warnings_resolved: 0,
              warnings_expired: 0,
              dedup_suppressions: 0,
              snapshots_emitted: 0,
              subscription_dispatches: 0,
              subscription_failures: 0,
              last_event_sequence: lastSequence,
            },
          },
    replay: null,
    queue: null,
    hints: {},
  };
}

function eventEnvelope(
  sequence: number,
  taskId: string,
  type: TaskLifecycleEvent["event_type"],
): RuntimeEnvelope {
  const payload = {
    event_type: type,
    event_id: `evt-${sequence}`,
    timestamp: 0,
    monotonic_ns: 0,
    runtime_id: "runtime-1",
    task_id: taskId,
    task_name: null,
    coroutine_name: null,
    parent_task_id: null,
    metadata: {},
  };
  return {
    protocol_version: "1.0",
    type: "runtime_event",
    timestamp: 0,
    sequence,
    payload: payload as unknown as Record<string, unknown>,
  };
}

/** Build a synthetic non-task ``runtime_event`` envelope. */
function customEventEnvelope(
  sequence: number,
  eventType: string,
  extra: Record<string, unknown> = {},
): RuntimeEnvelope {
  return {
    protocol_version: "1.0",
    type: "runtime_event",
    timestamp: 0,
    sequence,
    payload: { event_type: eventType, ...extra } as Record<string, unknown>,
  };
}

describe("RuntimeStore — hydration", () => {
  beforeEach(() => {
    useRuntimeStore.getState().reset();
  });

  it("seeds tasksById + taskIdsByState + runtimeId on hydrate", () => {
    useRuntimeStore.getState().hydrateSnapshot(snapshotResponse(10, { tasks: 3 }));
    const state = useRuntimeStore.getState();
    expect(Object.keys(state.tasksById)).toHaveLength(3);
    expect(state.taskIdsByState.running).toHaveLength(3);
    expect(state.lastSequence).toBe(10);
    expect(state.runtime.runtimeId).toBe("runtime-1");
    expect(state.stats.hydrations).toBe(1);
  });

  it("captures replay metadata", () => {
    useRuntimeStore.getState().hydrateSnapshot(snapshotResponse(7));
    expect(useRuntimeStore.getState().replay).toEqual({
      oldestRetainedSequence: 0,
      newestRetainedSequence: 7,
      windowHit: true,
    });
  });

  it("hydrates warnings + severity counts", () => {
    useRuntimeStore.getState().hydrateSnapshot(snapshotResponse(2, { warningIds: ["w1", "w2"] }));
    const state = useRuntimeStore.getState();
    expect(state.warnings.activeWarningIds).toEqual(["w1", "w2"]);
    expect(state.warnings.countsBySeverity.warning).toBe(2);
  });
});

describe("RuntimeStore — applyEnvelope", () => {
  beforeEach(() => {
    useRuntimeStore.getState().reset();
  });

  it("folds a runtime_event into tasksById + advances lastSequence", () => {
    useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "t1", "asyncio.task.created"));
    const state = useRuntimeStore.getState();
    expect(state.tasksById.t1?.state).toBe("created");
    expect(state.lastSequence).toBe(1);
    expect(state.stats.envelopesApplied).toBe(1);
  });

  it("drops duplicate envelopes + records the drop", () => {
    const env = eventEnvelope(1, "t1", "asyncio.task.created");
    useRuntimeStore.getState().applyEnvelope(env);
    useRuntimeStore.getState().applyEnvelope(env);
    expect(useRuntimeStore.getState().stats.duplicatesDropped).toBe(1);
  });

  it("drops stale envelopes whose sequence ≤ cursor", () => {
    useRuntimeStore.getState().applyEnvelope(eventEnvelope(5, "t1", "asyncio.task.created"));
    useRuntimeStore.getState().applyEnvelope(eventEnvelope(3, "t2", "asyncio.task.created"));
    expect(useRuntimeStore.getState().stats.staleDropped).toBe(1);
    expect(useRuntimeStore.getState().tasksById.t2).toBeUndefined();
  });

  it("guards against terminal-state regressions", () => {
    useRuntimeStore.getState().applyEnvelope(eventEnvelope(1, "t1", "asyncio.task.created"));
    useRuntimeStore.getState().applyEnvelope(eventEnvelope(2, "t1", "asyncio.task.completed"));
    useRuntimeStore.getState().applyEnvelope(eventEnvelope(3, "t1", "asyncio.task.created"));
    const state = useRuntimeStore.getState();
    expect(state.tasksById.t1?.state).toBe("completed");
    expect(state.stats.regressionsSuppressed).toBe(1);
  });

  it("processes heartbeat envelopes into runtime meta", () => {
    useRuntimeStore.getState().applyEnvelope({
      protocol_version: "1.0",
      type: "heartbeat",
      timestamp: 0,
      sequence: null,
      payload: { server_uptime_seconds: 42, connected_clients: 3 },
    });
    const state = useRuntimeStore.getState();
    expect(state.runtime.serverUptimeSeconds).toBe(42);
    expect(state.runtime.connectedClients).toBe(3);
  });

  it("processes warning_delta envelopes", () => {
    useRuntimeStore.getState().applyEnvelope({
      protocol_version: "1.0",
      type: "warning_delta",
      timestamp: 0,
      sequence: 1,
      payload: {
        change: "activated",
        sequence: 1,
        last_sequence: 1,
        warning: {
          warning_id: "w1",
          warning_key: "k1",
          warning_type: "stuck_task",
          severity: "critical",
          detector: "stuck",
          message: "stuck",
          created_sequence: null,
          created_monotonic_ns: 0,
          created_at_wall: 0,
          last_observed_sequence: null,
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
          runtime_id: null,
        },
      },
    });
    const state = useRuntimeStore.getState();
    expect(state.warnings.activeWarningIds).toEqual(["w1"]);
    expect(state.warnings.countsBySeverity.critical).toBe(1);
    expect(state.stats.warningDeltasApplied).toBe(1);
  });
});

describe("RuntimeStore — non-task runtime_event routing", () => {
  beforeEach(() => {
    useRuntimeStore.getState().reset();
  });

  it("does not silently drop a queue runtime_event", () => {
    useRuntimeStore
      .getState()
      .applyEnvelope(customEventEnvelope(1, "asyncio.queue.put", { queue_id: "q-1" }));
    const state = useRuntimeStore.getState();
    // Sequence + counters must advance.
    expect(state.lastSequence).toBe(1);
    expect(state.stats.envelopesApplied).toBe(1);
    // Heartbeat freshness must update.
    expect(state.connection.lastFrameAtMonotonicMs).toBeGreaterThan(0);
    // Histogram bucket lands at the namespace.subsystem prefix.
    expect(state.stats.runtimeEventsByCategory).toEqual({ "asyncio.queue": 1 });
    // The non-task event lands in the recent ring buffer.
    expect(state.recentRuntimeEvents).toHaveLength(1);
    expect(state.recentRuntimeEvents[0]).toMatchObject({
      sequence: 1,
      eventType: "asyncio.queue.put",
      category: "asyncio.queue",
      payload: { event_type: "asyncio.queue.put", queue_id: "q-1" },
    });
    // Task projections stay untouched.
    expect(state.tasksById).toEqual({});
    expect(state.events).toEqual([]);
    expect(state.stats.unhandledRuntimeEvents).toBe(0);
  });

  it.each([
    ["asyncio.queue.metrics.updated", "asyncio.queue"],
    ["asyncio.queue.contention.detected", "asyncio.queue"],
    ["asyncio.queue.saturation.detected", "asyncio.queue"],
    ["asyncio.gather.created", "asyncio.gather"],
    ["asyncio.gather.completed", "asyncio.gather"],
    ["asyncio.semaphore.acquired", "asyncio.semaphore"],
    ["asyncio.semaphore.contention.detected", "asyncio.semaphore"],
    ["asyncio.executor.work.submitted", "asyncio.executor"],
    ["asyncio.executor.work.completed", "asyncio.executor"],
    ["asyncio.loop.blocked", "asyncio.loop"],
    ["runtime.metric", "runtime.metric"],
    ["runtime.warning", "runtime.warning"],
    ["runtime.started", "runtime.started"],
  ])("routes %s into the recent-events ring + histogram bucket %s", (eventType, bucket) => {
    useRuntimeStore.getState().applyEnvelope(customEventEnvelope(1, eventType));
    const state = useRuntimeStore.getState();
    expect(state.recentRuntimeEvents).toHaveLength(1);
    expect(state.recentRuntimeEvents[0]?.eventType).toBe(eventType);
    expect(state.stats.runtimeEventsByCategory[bucket]).toBe(1);
    expect(state.tasksById).toEqual({});
    expect(state.events).toEqual([]);
  });

  it("interleaves task + non-task events without losing either", () => {
    const store = useRuntimeStore.getState();
    store.applyEnvelope(customEventEnvelope(1, "asyncio.queue.put"));
    store.applyEnvelope(eventEnvelope(2, "t1", "asyncio.task.created"));
    store.applyEnvelope(customEventEnvelope(3, "asyncio.gather.completed"));
    store.applyEnvelope(eventEnvelope(4, "t1", "asyncio.task.completed"));
    const state = useRuntimeStore.getState();
    expect(state.lastSequence).toBe(4);
    expect(state.stats.envelopesApplied).toBe(4);
    expect(state.tasksById.t1?.state).toBe("completed");
    // Task ring buffer only contains the two task events.
    expect(state.events).toHaveLength(2);
    // Recent ring contains every envelope.
    expect(state.recentRuntimeEvents.map((e) => e.eventType)).toEqual([
      "asyncio.queue.put",
      "asyncio.task.created",
      "asyncio.gather.completed",
      "asyncio.task.completed",
    ]);
    expect(state.stats.runtimeEventsByCategory).toEqual({
      "asyncio.queue": 1,
      "asyncio.task": 2,
      "asyncio.gather": 1,
    });
  });

  it("counts envelopes whose payload lacks event_type as unhandled", () => {
    useRuntimeStore.getState().applyEnvelope({
      protocol_version: "1.0",
      type: "runtime_event",
      timestamp: 0,
      sequence: 1,
      payload: { not_an_event_type: true } as Record<string, unknown>,
    });
    const state = useRuntimeStore.getState();
    expect(state.stats.unhandledRuntimeEvents).toBe(1);
    expect(state.stats.envelopesApplied).toBe(1);
    expect(state.lastSequence).toBe(1);
    expect(state.recentRuntimeEvents[0]?.eventType).toBe("unknown");
    expect(state.recentRuntimeEvents[0]?.category).toBe("");
    // Unknown events stay out of the histogram so it doesn't get
    // polluted with empty-bucket entries.
    expect(state.stats.runtimeEventsByCategory).toEqual({});
  });

  it("bounds the recent-events ring buffer", () => {
    const store = useRuntimeStore.getState();
    for (let i = 1; i <= 600; i += 1) {
      store.applyEnvelope(customEventEnvelope(i, "asyncio.queue.put"));
    }
    const state = useRuntimeStore.getState();
    // The store cap is 500; the most recent 500 events should remain.
    expect(state.recentRuntimeEvents).toHaveLength(500);
    expect(state.recentRuntimeEvents[0]?.sequence).toBe(101);
    expect(state.recentRuntimeEvents.at(-1)?.sequence).toBe(600);
    expect(state.stats.runtimeEventsByCategory["asyncio.queue"]).toBe(600);
  });
});

describe("RuntimeStore — replay_status envelope", () => {
  beforeEach(() => {
    useRuntimeStore.getState().reset();
  });

  it("sets replayActive once the first replay_status envelope arrives", () => {
    expect(useRuntimeStore.getState().runtime.replayActive).toBe(false);
    useRuntimeStore.getState().applyEnvelope({
      protocol_version: "1.0",
      type: "replay_status",
      timestamp: 0,
      sequence: null,
      payload: {
        recording: { bundle_id: "b1" },
        window: { max_sequence: 100 },
        playback: { state: "playing", speed: 1, last_sequence: 5 },
      },
    });
    const state = useRuntimeStore.getState();
    expect(state.runtime.replayActive).toBe(true);
    expect(state.runtime.replayPlaybackState).toBe("playing");
  });

  it("tracks playback state transitions across envelopes", () => {
    const store = useRuntimeStore.getState();
    store.applyEnvelope({
      protocol_version: "1.0",
      type: "replay_status",
      timestamp: 0,
      sequence: null,
      payload: { playback: { state: "playing" } },
    });
    expect(useRuntimeStore.getState().runtime.replayPlaybackState).toBe("playing");
    store.applyEnvelope({
      protocol_version: "1.0",
      type: "replay_status",
      timestamp: 0,
      sequence: null,
      payload: { playback: { state: "paused" } },
    });
    expect(useRuntimeStore.getState().runtime.replayPlaybackState).toBe("paused");
    store.applyEnvelope({
      protocol_version: "1.0",
      type: "replay_status",
      timestamp: 0,
      sequence: null,
      payload: { playback: { state: "stopped" } },
    });
    expect(useRuntimeStore.getState().runtime.replayPlaybackState).toBe("stopped");
  });

  it("never flips replayActive back to false on a malformed payload", () => {
    const store = useRuntimeStore.getState();
    store.applyEnvelope({
      protocol_version: "1.0",
      type: "replay_status",
      timestamp: 0,
      sequence: null,
      payload: { playback: { state: "playing" } },
    });
    expect(useRuntimeStore.getState().runtime.replayActive).toBe(true);
    // Malformed — no recognized fields.
    store.applyEnvelope({
      protocol_version: "1.0",
      type: "replay_status",
      timestamp: 0,
      sequence: null,
      payload: {},
    });
    // Stay sticky — the broadcaster sends this envelope every ~0.5s
    // and a single transient corruption shouldn't down-rev the badge.
    expect(useRuntimeStore.getState().runtime.replayActive).toBe(true);
    // Last good state is retained.
    expect(useRuntimeStore.getState().runtime.replayPlaybackState).toBe("playing");
  });

  it("ignores unknown playback state strings without crashing", () => {
    useRuntimeStore.getState().applyEnvelope({
      protocol_version: "1.0",
      type: "replay_status",
      timestamp: 0,
      sequence: null,
      payload: { playback: { state: "warp-9" } },
    });
    expect(useRuntimeStore.getState().runtime.replayActive).toBe(true);
    expect(useRuntimeStore.getState().runtime.replayPlaybackState).toBeNull();
  });

  it("refreshes the heartbeat-freshness marker", () => {
    const before = useRuntimeStore.getState().connection.lastFrameAtMonotonicMs;
    useRuntimeStore.getState().applyEnvelope({
      protocol_version: "1.0",
      type: "replay_status",
      timestamp: 0,
      sequence: null,
      payload: { playback: { state: "idle" } },
    });
    const after = useRuntimeStore.getState().connection.lastFrameAtMonotonicMs;
    expect(after).toBeGreaterThan(before);
  });
});


describe("RuntimeStore — replay batch", () => {
  beforeEach(() => {
    useRuntimeStore.getState().reset();
  });

  it("applies a sequenced batch of envelopes in order", () => {
    const batch = [
      eventEnvelope(1, "t1", "asyncio.task.created"),
      eventEnvelope(2, "t1", "asyncio.task.started"),
      eventEnvelope(3, "t1", "asyncio.task.completed"),
    ];
    useRuntimeStore.getState().applyReplayBatch(batch);
    const state = useRuntimeStore.getState();
    expect(state.tasksById.t1?.state).toBe("completed");
    expect(state.lastSequence).toBe(3);
  });
});

describe("RuntimeStore — selection", () => {
  beforeEach(() => {
    useRuntimeStore.getState().reset();
  });

  it("selectTask updates the selectedTaskId field", () => {
    useRuntimeStore.getState().selectTask("t99");
    expect(useRuntimeStore.getState().selectedTaskId).toBe("t99");
    useRuntimeStore.getState().selectTask(null);
    expect(useRuntimeStore.getState().selectedTaskId).toBeNull();
  });
});
