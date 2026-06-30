import { beforeEach, describe, expect, it } from "vitest";
import {
  appendMarker,
  markerFromPayload,
  reduceEventPayload,
  reduceHydration,
  useQueuePressureStore,
} from "@/dashboard/queues/QueuePressureStore";
import {
  makeContention,
  makeHydration,
  makePressureChange,
  makeRecord,
  makeSaturation,
  makeUpdated,
} from "@/dashboard/queues/__fixtures__/queuePressureFixtures";

beforeEach(() => {
  useQueuePressureStore.getState().reset();
});

describe("reduceHydration", () => {
  it("indexes records by id + preserves insertion order", () => {
    const reduced = reduceHydration(
      makeHydration({
        queues: [makeRecord({ queue_id: "q-1" }), makeRecord({ queue_id: "q-2" })],
      }),
    );
    expect(reduced.queueIds).toEqual(["q-1", "q-2"]);
    expect(reduced.recordsById["q-1"]?.queue_id).toBe("q-1");
  });
});

describe("reduceEventPayload", () => {
  it("applies metrics.updated as a record upsert", () => {
    const reduced = reduceEventPayload(
      {},
      makeUpdated({ queue_id: "q-1", current_size: 7, pressure_level: "warning" }),
    );
    expect(reduced).not.toBeNull();
    expect(reduced!["q-1"]?.occupancy.current_size).toBe(7);
    expect(reduced!["q-1"]?.pressure.level).toBe("warning");
  });

  it("drops pressure-change for an unknown queue id", () => {
    const reduced = reduceEventPayload({}, makePressureChange({ queue_id: "missing" }));
    expect(reduced).toBeNull();
  });

  it("applies contention to an existing record", () => {
    const initial = { "q-1": makeRecord({ queue_id: "q-1" }) };
    const reduced = reduceEventPayload(initial, makeContention({ blocked_producers: 4 }));
    expect(reduced).not.toBeNull();
    expect(reduced!["q-1"]?.contention.blocked_producers).toBe(4);
  });

  it("applies saturation to an existing record + lifts the sticky bit", () => {
    const initial = { "q-1": makeRecord({ queue_id: "q-1" }) };
    const reduced = reduceEventPayload(initial, makeSaturation({ occupancy_ratio: 0.99 }));
    expect(reduced).not.toBeNull();
    expect(reduced!["q-1"]?.pressure.saturated).toBe(true);
    expect(reduced!["q-1"]?.occupancy.occupancy_ratio).toBeCloseTo(0.99);
  });
});

describe("markerFromPayload", () => {
  it("returns null for metrics.updated", () => {
    expect(markerFromPayload(makeUpdated(), 123)).toBeNull();
  });

  it("builds a pressure-change marker", () => {
    const marker = markerFromPayload(makePressureChange(), 999);
    expect(marker?.kind).toBe("pressure-change");
    expect(marker?.severity).toBe("warning");
    expect(marker?.monotonicNs).toBe(999);
  });

  it("builds a saturated marker for saturation events", () => {
    const marker = markerFromPayload(makeSaturation(), 100);
    expect(marker?.severity).toBe("saturated");
    expect(marker?.kind).toBe("saturation");
  });
});

describe("appendMarker", () => {
  it("caps the buffer + reports evictions", () => {
    const buffer = Array.from({ length: 3 }, (_, i) => ({
      id: `m-${i}`,
      queueId: "q-1",
      kind: "pressure-change" as const,
      severity: "warning" as const,
      monotonicNs: i,
      label: `m-${i}`,
    }));
    const { next, evicted } = appendMarker(
      buffer,
      {
        id: "m-new",
        queueId: "q-1",
        kind: "saturation",
        severity: "saturated",
        monotonicNs: 999,
        label: "n",
      },
      3,
    );
    expect(next).toHaveLength(3);
    expect(next[next.length - 1].id).toBe("m-new");
    expect(next[0].id).toBe("m-1");
    expect(evicted).toBe(1);
  });
});

describe("useQueuePressureStore actions", () => {
  it("hydrateSnapshot bumps stats + flips status to ready", () => {
    useQueuePressureStore
      .getState()
      .hydrateSnapshot(makeHydration({ queues: [makeRecord({ queue_id: "q-a" })] }));
    const state = useQueuePressureStore.getState();
    expect(state.status).toBe("ready");
    expect(state.queueIds).toEqual(["q-a"]);
    expect(state.stats.hydrationsApplied).toBe(1);
  });

  it("applyEventPayload registers a marker for pressure-change", () => {
    useQueuePressureStore
      .getState()
      .hydrateSnapshot(makeHydration({ queues: [makeRecord({ queue_id: "q-1" })] }));
    useQueuePressureStore.getState().applyEventPayload(makePressureChange({ queue_id: "q-1" }));
    const state = useQueuePressureStore.getState();
    expect(state.markers).toHaveLength(1);
    expect(state.markers[0].kind).toBe("pressure-change");
  });

  it("applyEventPayload increments dropped stats when the queue is unknown", () => {
    useQueuePressureStore.getState().applyEventPayload(makePressureChange({ queue_id: "ghost" }));
    expect(useQueuePressureStore.getState().stats.eventsDropped).toBe(1);
  });

  it("setMarkerCapacity ignores zero/negative inputs", () => {
    const prior = useQueuePressureStore.getState().markerCapacity;
    useQueuePressureStore.getState().setMarkerCapacity(0);
    expect(useQueuePressureStore.getState().markerCapacity).toBe(prior);
  });
});
