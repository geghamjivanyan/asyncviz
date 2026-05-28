import { beforeEach, describe, expect, it } from "vitest";
import {
  appendMarker,
  markerFromPayload,
  reduceEventPayload,
  reduceHydration,
  useSemaphoreContentionStore,
} from "@/dashboard/semaphores/SemaphoreContentionStore";
import {
  makeAcquired,
  makeContention,
  makeCreated,
  makeHydration,
  makeIdentity,
  makeReleased,
  makeCancelled,
} from "@/dashboard/semaphores/__fixtures__/semaphoreContentionFixtures";

beforeEach(() => {
  useSemaphoreContentionStore.getState().reset();
});

describe("reduceHydration", () => {
  it("indexes records by id + preserves insertion order", () => {
    const reduced = reduceHydration(
      makeHydration({
        semaphores: [makeIdentity({ semaphore_id: "s-1" }), makeIdentity({ semaphore_id: "s-2" })],
      }),
    );
    expect(reduced.semaphoreIds).toEqual(["s-1", "s-2"]);
    expect(reduced.recordsById["s-1"]?.semaphoreId).toBe("s-1");
  });
});

describe("reduceEventPayload", () => {
  it("scaffolds a record on first event for an unknown semaphore", () => {
    const reduced = reduceEventPayload({}, makeCreated({ semaphore_id: "s-new" }));
    expect(reduced).not.toBeNull();
    expect(reduced!["s-new"]?.semaphoreId).toBe("s-new");
  });

  it("applies acquired as snapshot + acquire count bump", () => {
    const reduced = reduceEventPayload(
      {},
      makeAcquired({ blocked: true, wait_seconds: 0.4 }),
    );
    expect(reduced!["s-1"]?.acquireCount).toBe(1);
    expect(reduced!["s-1"]?.blockedAcquireCount).toBe(1);
    expect(reduced!["s-1"]?.meanWaitSeconds).toBeCloseTo(0.4);
  });

  it("applies released as snapshot + release count bump", () => {
    const reduced = reduceEventPayload({}, makeReleased());
    expect(reduced!["s-1"]?.releaseCount).toBe(1);
    expect(reduced!["s-1"]?.currentValue).toBe(4);
  });

  it("applies contention.detected with flat fields preferred over snapshot", () => {
    const reduced = reduceEventPayload(
      {},
      makeContention({ waiter_count: 3, current_value: 0 }),
    );
    expect(reduced!["s-1"]?.waiterCount).toBe(3);
    expect(reduced!["s-1"]?.currentValue).toBe(0);
    expect(reduced!["s-1"]?.peakWaiterCount).toBe(3);
  });

  it("applies wait.cancelled with snapshot + cancelled count bump", () => {
    const reduced = reduceEventPayload({}, makeCancelled());
    expect(reduced!["s-1"]?.cancelledWaitCount).toBe(1);
  });

  it("tracks running mean wait seconds across multiple blocked acquires", () => {
    let records = reduceEventPayload(
      {},
      makeAcquired({ blocked: true, wait_seconds: 0.2 }),
    )!;
    records = reduceEventPayload(
      records,
      makeAcquired({ blocked: true, wait_seconds: 0.6 }),
    )!;
    expect(records["s-1"]?.blockedAcquireCount).toBe(2);
    expect(records["s-1"]?.meanWaitSeconds).toBeCloseTo(0.4);
    expect(records["s-1"]?.maxWaitSeconds).toBeCloseTo(0.6);
  });
});

describe("markerFromPayload", () => {
  it("returns null for created", () => {
    expect(markerFromPayload(makeCreated(), 100)).toBeNull();
  });

  it("emits a contention marker for contention.detected", () => {
    const marker = markerFromPayload(makeContention({ waiter_count: 2 }), 999);
    expect(marker?.kind).toBe("contention");
    expect(marker?.severity).toBe("warning");
    expect(marker?.monotonicNs).toBe(999);
  });

  it("emits a wait-cancelled marker for wait.cancelled", () => {
    const marker = markerFromPayload(makeCancelled(), 100);
    expect(marker?.kind).toBe("wait-cancelled");
  });

  it("emits a saturation marker when blocked acquire drains last permit", () => {
    const marker = markerFromPayload(
      makeAcquired({
        blocked: true,
        snapshot: { current_value: 0, waiter_count: 1, initial_value: 4, bound_value: null },
      }),
      100,
    );
    expect(marker?.kind).toBe("saturation");
    expect(marker?.severity).toBe("saturated");
  });
});

describe("appendMarker", () => {
  it("caps + reports evictions", () => {
    const buffer = Array.from({ length: 3 }, (_, i) => ({
      id: `m-${i}`,
      semaphoreId: "s-1",
      kind: "contention" as const,
      severity: "warning" as const,
      monotonicNs: i,
      label: `m-${i}`,
    }));
    const { next, evicted } = appendMarker(
      buffer,
      {
        id: "m-new",
        semaphoreId: "s-1",
        kind: "saturation",
        severity: "saturated",
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

describe("useSemaphoreContentionStore actions", () => {
  it("hydrateSnapshot bumps stats + flips status to ready", () => {
    useSemaphoreContentionStore.getState().hydrateSnapshot(
      makeHydration({ semaphores: [makeIdentity({ semaphore_id: "s-a" })] }),
    );
    const state = useSemaphoreContentionStore.getState();
    expect(state.status).toBe("ready");
    expect(state.semaphoreIds).toEqual(["s-a"]);
    expect(state.stats.hydrationsApplied).toBe(1);
  });

  it("applyEventPayload registers a marker on contention.detected", () => {
    useSemaphoreContentionStore.getState().hydrateSnapshot(
      makeHydration({ semaphores: [makeIdentity({ semaphore_id: "s-1" })] }),
    );
    useSemaphoreContentionStore.getState().applyEventPayload(makeContention());
    const state = useSemaphoreContentionStore.getState();
    expect(state.markers).toHaveLength(1);
    expect(state.markers[0].kind).toBe("contention");
  });

  it("lazily scaffolds a new semaphore from a streamed event after hydration", () => {
    useSemaphoreContentionStore.getState().hydrateSnapshot(makeHydration());
    useSemaphoreContentionStore.getState().applyEventPayload(
      makeAcquired({ semaphore_id: "s-late" }),
    );
    const state = useSemaphoreContentionStore.getState();
    expect(state.semaphoreIds).toContain("s-late");
  });

  it("setMarkerCapacity ignores invalid input", () => {
    const prior = useSemaphoreContentionStore.getState().markerCapacity;
    useSemaphoreContentionStore.getState().setMarkerCapacity(0);
    expect(useSemaphoreContentionStore.getState().markerCapacity).toBe(prior);
  });
});
