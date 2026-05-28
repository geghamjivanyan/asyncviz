/**
 * Unit tests for the pure store → header-snapshot projection.
 *
 * Everything in this file works against synthetic inputs — no React,
 * no Zustand. The projection's responsibility is to be deterministic
 * and replay-safe.
 */

import { describe, expect, it } from "vitest";
import {
  projectClock,
  projectConnection,
  projectEventRate,
  projectHealth,
  projectMetricsHeader,
  projectReplay,
  projectTaskCounts,
  projectThroughput,
  projectWarnings,
  type ProjectionInputs,
} from "@/dashboard/metrics/selectors/projectSummaries";
import { INITIAL_RECONCILIATION_STATS, INITIAL_RUNTIME_META } from "@/state/runtime/models";

function makeInputs(overrides: Partial<ProjectionInputs> = {}): ProjectionInputs {
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
      serverUptimeSeconds: 60,
      connectedClients: 2,
      clock: {
        runtime_id: "rt-1",
        started_at_wall_seconds: 0,
        started_at_monotonic_ns: 0,
        wall_now_seconds: 60,
        wall_now_iso: "1970-01-01T00:01:00Z",
        monotonic_now_ns: 0,
        monotonic_now_seconds: 60,
        uptime_seconds: 60,
        uptime_ns: 0,
        current_sequence: 100,
      },
    },
    replay: {
      oldestRetainedSequence: 0,
      newestRetainedSequence: 200,
      windowHit: true,
    },
    timeline: {
      segmentsById: {},
      activeSegmentsByTaskId: {},
      segmentIdsByTaskId: {},
      lastSequence: 0,
    },
    warnings: {
      warningsById: {},
      activeWarningIds: [],
      resolvedWarningIds: [],
      countsBySeverity: { info: 0, warning: 0, error: 0, critical: 0 },
    },
    metrics: { aggregate: null, deltaCounts: {} },
    stats: {
      ...INITIAL_RECONCILIATION_STATS,
      envelopesApplied: 50,
      hydrations: 1,
    },
    tasksById: {},
    taskIdsByState: {
      created: [],
      running: [],
      waiting: [],
      completed: [],
      cancelled: [],
      failed: [],
    },
    lastSequence: 100,
    nowMs: 1_000,
    envelopesPerSecond: 5,
    ...overrides,
  };
}

describe("projectConnection", () => {
  it("derives lastFrameAgoMs from nowMs - lastFrame", () => {
    const summary = projectConnection(
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
    expect(summary.lastFrameAgoMs).toBe(1000);
  });

  it("returns null lastFrameAgoMs when no frame seen", () => {
    const summary = projectConnection(makeInputs());
    expect(summary.lastFrameAgoMs).toBeNull();
  });

  it("isLive is true only during live/replay phases", () => {
    expect(
      projectConnection(
        makeInputs({
          connection: {
            phase: "live",
            state: "open",
            reconnectAttempts: 0,
            lastFrameAtMonotonicMs: 0,
          },
        }),
      ).isLive,
    ).toBe(true);
    expect(
      projectConnection(
        makeInputs({
          connection: {
            phase: "replaying",
            state: "open",
            reconnectAttempts: 0,
            lastFrameAtMonotonicMs: 0,
          },
        }),
      ).isLive,
    ).toBe(true);
    expect(
      projectConnection(
        makeInputs({
          connection: {
            phase: "reconnecting",
            state: "connecting",
            reconnectAttempts: 3,
            lastFrameAtMonotonicMs: 0,
          },
        }),
      ).isLive,
    ).toBe(false);
  });
});

describe("projectReplay", () => {
  it("computes cursorProgress from lastSequence / newest", () => {
    const summary = projectReplay(
      makeInputs({
        lastSequence: 50,
        replay: { windowHit: true, oldestRetainedSequence: 0, newestRetainedSequence: 100 },
      }),
    );
    expect(summary.cursorProgress).toBeCloseTo(0.5);
  });

  it("clamps cursorProgress to [0, 1]", () => {
    const summary = projectReplay(
      makeInputs({
        lastSequence: 200,
        replay: { windowHit: true, oldestRetainedSequence: 0, newestRetainedSequence: 100 },
      }),
    );
    expect(summary.cursorProgress).toBe(1);
  });

  it("propagates windowHit + isReplaying flags", () => {
    const summary = projectReplay(
      makeInputs({
        replay: { windowHit: false, oldestRetainedSequence: null, newestRetainedSequence: null },
        connection: {
          phase: "replaying",
          state: "open",
          reconnectAttempts: 0,
          lastFrameAtMonotonicMs: 0,
        },
      }),
    );
    expect(summary.windowHit).toBe(false);
    expect(summary.isReplaying).toBe(true);
  });
});

describe("projectWarnings", () => {
  it("aggregates total + highest severity", () => {
    const summary = projectWarnings(
      makeInputs({
        warnings: {
          warningsById: {},
          activeWarningIds: [],
          resolvedWarningIds: [],
          countsBySeverity: { info: 1, warning: 2, error: 3, critical: 0 },
        },
      }),
    );
    expect(summary.total).toBe(6);
    expect(summary.highest).toBe("error");
  });

  it("returns null highest when there are no warnings", () => {
    const summary = projectWarnings(makeInputs());
    expect(summary.highest).toBeNull();
  });
});

describe("projectTaskCounts", () => {
  it("sums every bucket into total + terminal", () => {
    const summary = projectTaskCounts(
      makeInputs({
        taskIdsByState: {
          created: ["c1"],
          running: ["r1", "r2"],
          waiting: ["w1"],
          completed: ["x1"],
          cancelled: ["x2"],
          failed: ["x3"],
        },
      }),
    );
    expect(summary.total).toBe(7);
    expect(summary.active).toBe(2);
    expect(summary.waiting).toBe(1);
    expect(summary.terminal).toBe(3);
  });
});

describe("projectThroughput", () => {
  it("returns zero-state when there's no aggregate", () => {
    const summary = projectThroughput(makeInputs());
    expect(summary.tasksPerSecond).toBe(0);
    expect(summary.windowSeconds).toBe(0);
  });

  it("reads throughput from the metrics aggregate", () => {
    const summary = projectThroughput(
      makeInputs({
        metrics: {
          aggregate: {
            schema_version: 1,
            generated_at: 0,
            generated_at_monotonic_ns: 0,
            runtime_id: "rt-1",
            last_sequence: 100,
            runtime_uptime_seconds: 60,
            counts: {
              total: 0,
              active: 0,
              waiting: 0,
              completed: 0,
              cancelled: 0,
              failed: 0,
              terminal: 0,
            },
            throughput: {
              tasks_per_second: 12.5,
              completions_per_second: 11,
              cancellations_per_second: 0.5,
              failures_per_second: 1,
              window_seconds: 5,
            },
            durations: {
              completed: {
                count: 0,
                total_seconds: 0,
                min_seconds: 0,
                max_seconds: 0,
                mean_seconds: 0,
                histogram: {
                  count: 0,
                  min_value: 0,
                  max_value: 0,
                  mean: 0,
                  p50: 0,
                  p95: 0,
                  p99: 0,
                  sum_value: 0,
                  samples: 0,
                },
              },
              cancelled: {
                count: 0,
                total_seconds: 0,
                min_seconds: 0,
                max_seconds: 0,
                mean_seconds: 0,
                histogram: {
                  count: 0,
                  min_value: 0,
                  max_value: 0,
                  mean: 0,
                  p50: 0,
                  p95: 0,
                  p99: 0,
                  sum_value: 0,
                  samples: 0,
                },
              },
              failed: {
                count: 0,
                total_seconds: 0,
                min_seconds: 0,
                max_seconds: 0,
                mean_seconds: 0,
                histogram: {
                  count: 0,
                  min_value: 0,
                  max_value: 0,
                  mean: 0,
                  p50: 0,
                  p95: 0,
                  p99: 0,
                  sum_value: 0,
                  samples: 0,
                },
              },
              overall: {
                count: 0,
                total_seconds: 0,
                min_seconds: 0,
                max_seconds: 0,
                mean_seconds: 0,
                histogram: {
                  count: 0,
                  min_value: 0,
                  max_value: 0,
                  mean: 0,
                  p50: 0,
                  p95: 0,
                  p99: 0,
                  sum_value: 0,
                  samples: 0,
                },
              },
            },
            coroutines: [],
            lineage: {
              root_count: 0,
              max_depth: 0,
              average_fanout: 0,
              largest_tree_size: 0,
              largest_tree_root_id: null,
              cancellations_propagated: 0,
            },
            cancellations_by_origin: {},
            longest_tasks: [],
            shortest_tasks: [],
            timeline: null,
            self_metrics: {
              events_observed: 0,
              events_stale: 0,
              events_duplicate: 0,
              snapshots_emitted: 0,
              rebuilds_completed: 0,
              subscription_dispatches: 0,
              subscription_failures: 0,
              last_event_sequence: 0,
            },
          },
          deltaCounts: {},
        },
      }),
    );
    expect(summary.tasksPerSecond).toBe(12.5);
    expect(summary.windowSeconds).toBe(5);
  });
});

describe("projectEventRate", () => {
  it("passes through reconciliation counters", () => {
    const summary = projectEventRate(
      makeInputs({
        stats: {
          ...INITIAL_RECONCILIATION_STATS,
          envelopesApplied: 100,
          duplicatesDropped: 2,
          staleDropped: 3,
          protocolErrors: 1,
          hydrations: 1,
        },
        envelopesPerSecond: 12.34,
      }),
    );
    expect(summary.envelopesApplied).toBe(100);
    expect(summary.staleDropped).toBe(3);
    expect(summary.protocolErrors).toBe(1);
    expect(summary.envelopesPerSecond).toBeCloseTo(12.34);
  });
});

describe("projectClock", () => {
  it("returns 0 uptime when there's no clock snapshot", () => {
    const summary = projectClock(
      makeInputs({
        runtime: INITIAL_RUNTIME_META,
      }),
    );
    expect(summary.uptimeSeconds).toBe(0);
    expect(summary.wallNowMs).toBeNull();
  });
});

describe("projectHealth", () => {
  it("returns healthy when live + no warnings", () => {
    const inputs = makeInputs();
    const warnings = projectWarnings(inputs);
    const connection = projectConnection(inputs);
    const replay = projectReplay(inputs);
    const health = projectHealth(inputs, warnings, connection, replay);
    expect(health.level).toBe("healthy");
  });

  it("returns unavailable when a critical warning is active", () => {
    const inputs = makeInputs({
      warnings: {
        warningsById: {},
        activeWarningIds: ["w1"],
        resolvedWarningIds: [],
        countsBySeverity: { info: 0, warning: 0, error: 0, critical: 1 },
      },
    });
    const health = projectHealth(
      inputs,
      projectWarnings(inputs),
      projectConnection(inputs),
      projectReplay(inputs),
    );
    expect(health.level).toBe("unavailable");
    expect(health.hasCriticalWarning).toBe(true);
  });

  it("returns degraded when an error warning is active", () => {
    const inputs = makeInputs({
      warnings: {
        warningsById: {},
        activeWarningIds: ["w1"],
        resolvedWarningIds: [],
        countsBySeverity: { info: 0, warning: 0, error: 1, critical: 0 },
      },
    });
    const health = projectHealth(
      inputs,
      projectWarnings(inputs),
      projectConnection(inputs),
      projectReplay(inputs),
    );
    expect(health.level).toBe("degraded");
  });

  it("returns unavailable when the replay window was missed", () => {
    const inputs = makeInputs({
      replay: { windowHit: false, oldestRetainedSequence: null, newestRetainedSequence: null },
    });
    const health = projectHealth(
      inputs,
      projectWarnings(inputs),
      projectConnection(inputs),
      projectReplay(inputs),
    );
    expect(health.level).toBe("unavailable");
  });

  it("returns starting while hydrating", () => {
    const inputs = makeInputs({
      connection: {
        phase: "hydrating",
        state: "connecting",
        reconnectAttempts: 0,
        lastFrameAtMonotonicMs: 0,
      },
    });
    const health = projectHealth(
      inputs,
      projectWarnings(inputs),
      projectConnection(inputs),
      projectReplay(inputs),
    );
    expect(health.level).toBe("starting");
  });
});

describe("projectMetricsHeader", () => {
  it("produces a stable signature for identical inputs", () => {
    const inputs = makeInputs();
    const a = projectMetricsHeader(inputs);
    const b = projectMetricsHeader(inputs);
    expect(a.signature).toEqual(b.signature);
  });

  it("signature changes when the underlying state changes", () => {
    const a = projectMetricsHeader(makeInputs());
    const b = projectMetricsHeader(
      makeInputs({
        taskIdsByState: {
          created: [],
          running: ["r1"],
          waiting: [],
          completed: [],
          cancelled: [],
          failed: [],
        },
      }),
    );
    expect(a.signature).not.toEqual(b.signature);
  });

  it("composes every sub-projection", () => {
    const snapshot = projectMetricsHeader(makeInputs());
    expect(snapshot.connection).toBeDefined();
    expect(snapshot.replay).toBeDefined();
    expect(snapshot.warnings).toBeDefined();
    expect(snapshot.taskCounts).toBeDefined();
    expect(snapshot.throughput).toBeDefined();
    expect(snapshot.eventRate).toBeDefined();
    expect(snapshot.clock).toBeDefined();
    expect(snapshot.health).toBeDefined();
  });
});
