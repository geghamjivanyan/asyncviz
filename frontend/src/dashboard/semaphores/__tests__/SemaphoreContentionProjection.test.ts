import { describe, expect, it } from "vitest";
import {
  describeMarker,
  projectMarkersInWindow,
  projectRecord,
  projectSemaphoreContention,
} from "@/dashboard/semaphores/SemaphoreContentionProjection";
import type { SemaphoreContentionMarker } from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import { makeRecord } from "@/dashboard/semaphores/__fixtures__/semaphoreContentionFixtures";

describe("projectRecord", () => {
  it("derives calm for an idle semaphore", () => {
    const view = projectRecord(makeRecord({ currentValue: 4, waiterCount: 0 }));
    expect(view.severity).toBe("calm");
    expect(view.permitsInUse).toBe(0);
    expect(view.utilizationRatio).toBe(0);
  });

  it("escalates to saturated when permits are exhausted with waiters", () => {
    const view = projectRecord(
      makeRecord({ currentValue: 0, waiterCount: 1 }),
    );
    expect(view.severity).toBe("saturated");
    expect(view.saturated).toBe(true);
    expect(view.permitsInUse).toBe(4);
  });

  it("warns on high utilization without waiters", () => {
    const view = projectRecord(
      makeRecord({ currentValue: 1, waiterCount: 0 }),
    );
    expect(view.severity).toBe("warning");
  });

  it("falls back to record.name then id when no display name", () => {
    expect(projectRecord(makeRecord({ semaphoreId: "s-42" })).displayName).toBe("s-42");
    expect(
      projectRecord(makeRecord({ semaphoreId: "s-42", name: "db-pool" })).displayName,
    ).toBe("db-pool");
    expect(
      projectRecord(makeRecord({ semaphoreId: "s-42" }), "override").displayName,
    ).toBe("override");
  });

  it("clamps permitsInUse to [0, initialValue]", () => {
    // currentValue null treats as initial → permits in use = 0
    const view = projectRecord(makeRecord({ currentValue: null }));
    expect(view.permitsInUse).toBe(0);
  });
});

describe("projectSemaphoreContention", () => {
  it("sorts by severity descending then by utilization", () => {
    const records = [
      makeRecord({ semaphoreId: "s-calm", currentValue: 4, waiterCount: 0 }),
      makeRecord({
        semaphoreId: "s-warn",
        currentValue: 1,
        waiterCount: 0,
      }),
      makeRecord({
        semaphoreId: "s-sat",
        currentValue: 0,
        waiterCount: 2,
      }),
    ];
    const { bySeverityDescending, alarmCount } = projectSemaphoreContention({
      records,
    });
    expect(bySeverityDescending.map((v) => v.semaphoreId)).toEqual([
      "s-sat",
      "s-warn",
      "s-calm",
    ]);
    expect(alarmCount).toBe(2);
  });

  it("returns empty for empty input", () => {
    const projection = projectSemaphoreContention({ records: [] });
    expect(projection.views).toEqual([]);
    expect(projection.alarmCount).toBe(0);
  });
});

describe("projectMarkersInWindow", () => {
  const markers: SemaphoreContentionMarker[] = [
    {
      id: "a",
      semaphoreId: "s-1",
      kind: "contention",
      severity: "warning",
      monotonicNs: 100,
      label: "a",
    },
    {
      id: "b",
      semaphoreId: "s-1",
      kind: "saturation",
      severity: "saturated",
      monotonicNs: 500,
      label: "b",
    },
    {
      id: "c",
      semaphoreId: "s-2",
      kind: "wait-cancelled",
      severity: "warning",
      monotonicNs: 900,
      label: "c",
    },
  ];

  it("returns markers within window", () => {
    const slice = projectMarkersInWindow({ markers, startNs: 200, endNs: 800 });
    expect(slice.map((m) => m.id)).toEqual(["b"]);
  });

  it("respects limit cap", () => {
    expect(projectMarkersInWindow({ markers, limit: 2 })).toHaveLength(2);
  });
});

describe("describeMarker", () => {
  it("joins kind + detail", () => {
    expect(
      describeMarker({
        id: "a",
        semaphoreId: "s-1",
        kind: "saturation",
        severity: "saturated",
        monotonicNs: 0,
        label: "Saturated",
        detail: "2 waiting",
      }),
    ).toBe("Saturation: 2 waiting");
  });
});
