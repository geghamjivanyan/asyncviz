import { beforeEach, describe, expect, it } from "vitest";
import {
  appendMarker,
  markerFromPayload,
  reduceEventPayload,
  reduceHydration,
  useExecutorActivityStore,
} from "@/dashboard/executors/ExecutorActivityStore";
import {
  makeContention,
  makeHydration,
  makeLatencySpike,
  makeRecord,
  makeSaturationChanged,
  makeUpdated,
} from "@/dashboard/executors/__fixtures__/executorActivityFixtures";

beforeEach(() => {
  useExecutorActivityStore.getState().reset();
});

describe("reduceHydration", () => {
  it("indexes records by id + preserves insertion order", () => {
    const reduced = reduceHydration(
      makeHydration({
        executors: [
          makeRecord({ executor_id: "e-1" }),
          makeRecord({ executor_id: "e-2" }),
        ],
      }),
    );
    expect(reduced.executorIds).toEqual(["e-1", "e-2"]);
    expect(reduced.recordsById["e-1"]?.executor_id).toBe("e-1");
  });
});

describe("reduceEventPayload", () => {
  it("applies metrics.updated as a record upsert", () => {
    const reduced = reduceEventPayload(
      {},
      makeUpdated({
        active_workers: 3,
        utilization_ratio: 0.75,
        saturation_level: "warning",
      }),
    );
    expect(reduced).not.toBeNull();
    const r = reduced!["e-1"];
    expect(r?.utilization.active_workers).toBe(3);
    expect(r?.utilization.utilization_ratio).toBeCloseTo(0.75);
    expect(r?.saturation.level).toBe("warning");
  });

  it("drops saturation.changed for an unknown executor", () => {
    expect(reduceEventPayload({}, makeSaturationChanged({ executor_id: "ghost" })))
      .toBeNull();
  });

  it("applies contention to an existing record", () => {
    const initial = { "e-1": makeRecord({ executor_id: "e-1" }) };
    const reduced = reduceEventPayload(
      initial,
      makeContention({ active_workers: 5, utilization_ratio: 1.0 }),
    );
    expect(reduced!["e-1"]?.utilization.active_workers).toBe(5);
    expect(reduced!["e-1"]?.utilization.utilization_ratio).toBe(1.0);
  });

  it("applies latency spike preserving the max value", () => {
    const initial = {
      "e-1": makeRecord({
        executor_id: "e-1",
        submission_latency: {
          count: 1,
          mean_seconds: 0.1,
          p50_seconds: 0.1,
          p95_seconds: 0.1,
          p99_seconds: 0.1,
          max_seconds: 0.3,
        },
      }),
    };
    const reduced = reduceEventPayload(
      initial,
      makeLatencySpike({ submission_latency_seconds: 0.4 }),
    );
    expect(reduced!["e-1"]?.submission_latency.max_seconds).toBeCloseTo(0.4);
  });
});

describe("markerFromPayload", () => {
  it("returns null for metrics.updated", () => {
    expect(markerFromPayload(makeUpdated(), 100)).toBeNull();
  });

  it("emits a saturation-changed marker with derived severity", () => {
    const marker = markerFromPayload(
      makeSaturationChanged({
        new_level: "critical",
        utilization_ratio: 1.0,
        backlog: 5,
      }),
      999,
    );
    expect(marker?.kind).toBe("saturation-changed");
    expect(marker?.severity).toBe("saturated");
  });

  it("emits a contention marker", () => {
    const marker = markerFromPayload(makeContention(), 100);
    expect(marker?.kind).toBe("contention");
  });

  it("emits a latency-spike marker", () => {
    const marker = markerFromPayload(makeLatencySpike(), 100);
    expect(marker?.kind).toBe("latency-spike");
  });
});

describe("appendMarker", () => {
  it("caps + reports evictions", () => {
    const buffer = Array.from({ length: 3 }, (_, i) => ({
      id: `m-${i}`,
      executorId: "e-1",
      kind: "contention" as const,
      severity: "warning" as const,
      monotonicNs: i,
      label: `m-${i}`,
    }));
    const { next, evicted } = appendMarker(
      buffer,
      {
        id: "m-new",
        executorId: "e-1",
        kind: "saturation-changed",
        severity: "critical",
        monotonicNs: 999,
        label: "n",
      },
      3,
    );
    expect(next).toHaveLength(3);
    expect(next[next.length - 1].id).toBe("m-new");
    expect(evicted).toBe(1);
  });
});

describe("useExecutorActivityStore actions", () => {
  it("hydrateSnapshot bumps stats + flips status to ready", () => {
    useExecutorActivityStore.getState().hydrateSnapshot(
      makeHydration({ executors: [makeRecord({ executor_id: "e-a" })] }),
    );
    const state = useExecutorActivityStore.getState();
    expect(state.status).toBe("ready");
    expect(state.executorIds).toEqual(["e-a"]);
    expect(state.stats.hydrationsApplied).toBe(1);
  });

  it("applyEventPayload registers a marker on saturation.changed", () => {
    useExecutorActivityStore.getState().hydrateSnapshot(
      makeHydration({ executors: [makeRecord({ executor_id: "e-1" })] }),
    );
    useExecutorActivityStore
      .getState()
      .applyEventPayload(makeSaturationChanged({ executor_id: "e-1" }));
    const state = useExecutorActivityStore.getState();
    expect(state.markers).toHaveLength(1);
    expect(state.markers[0].kind).toBe("saturation-changed");
  });

  it("applyEventPayload increments dropped stats for unknown executor on non-updated events", () => {
    useExecutorActivityStore
      .getState()
      .applyEventPayload(makeContention({ executor_id: "ghost" }));
    expect(useExecutorActivityStore.getState().stats.eventsDropped).toBe(1);
  });

  it("setMarkerCapacity ignores zero/negative inputs", () => {
    const prior = useExecutorActivityStore.getState().markerCapacity;
    useExecutorActivityStore.getState().setMarkerCapacity(0);
    expect(useExecutorActivityStore.getState().markerCapacity).toBe(prior);
  });
});
