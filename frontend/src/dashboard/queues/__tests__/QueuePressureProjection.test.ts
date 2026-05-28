import { describe, expect, it } from "vitest";
import {
  describeMarker,
  projectMarkersInWindow,
  projectQueuePressure,
  projectRecord,
} from "@/dashboard/queues/QueuePressureProjection";
import type { QueuePressureMarker } from "@/dashboard/queues/models/QueuePressureModels";
import { makeRecord } from "@/dashboard/queues/__fixtures__/queuePressureFixtures";

describe("projectRecord", () => {
  it("derives severity from level + saturated bit", () => {
    const view = projectRecord(
      makeRecord({ pressure: { ...makeRecord().pressure, level: "warning" } }),
    );
    expect(view.severity).toBe("warning");
  });

  it("escalates to saturated when the sticky bit is set", () => {
    const view = projectRecord(
      makeRecord({
        pressure: { ...makeRecord().pressure, level: "critical", saturated: true },
      }),
    );
    expect(view.severity).toBe("saturated");
  });

  it("uses display name fallback when no override is provided", () => {
    const view = projectRecord(makeRecord({ queue_id: "q-42" }));
    expect(view.displayName).toBe("q-42");
  });

  it("honors a per-queue display name override", () => {
    const view = projectRecord(makeRecord({ queue_id: "q-42" }), "orders");
    expect(view.displayName).toBe("orders");
  });
});

describe("projectQueuePressure", () => {
  it("sorts by severity descending, then by pressure score", () => {
    const records = [
      makeRecord({
        queue_id: "q-calm",
        pressure: { ...makeRecord().pressure, level: "calm", pressure_score: 0.1 },
      }),
      makeRecord({
        queue_id: "q-warn",
        pressure: { ...makeRecord().pressure, level: "warning", pressure_score: 0.7 },
      }),
      makeRecord({
        queue_id: "q-sat",
        pressure: {
          ...makeRecord().pressure,
          level: "critical",
          pressure_score: 0.95,
          saturated: true,
        },
      }),
    ];
    const { bySeverityDescending, alarmCount } = projectQueuePressure({ records });
    expect(bySeverityDescending.map((v) => v.queueId)).toEqual([
      "q-sat",
      "q-warn",
      "q-calm",
    ]);
    expect(alarmCount).toBe(2);
  });

  it("returns an empty projection for an empty input", () => {
    const projection = projectQueuePressure({ records: [] });
    expect(projection.views).toEqual([]);
    expect(projection.bySeverityDescending).toEqual([]);
    expect(projection.alarmCount).toBe(0);
  });
});

describe("projectMarkersInWindow", () => {
  const markers: QueuePressureMarker[] = [
    { id: "a", queueId: "q-1", kind: "pressure-change", severity: "warning", monotonicNs: 100, label: "a" },
    { id: "b", queueId: "q-1", kind: "saturation", severity: "saturated", monotonicNs: 500, label: "b" },
    { id: "c", queueId: "q-2", kind: "contention", severity: "warning", monotonicNs: 900, label: "c" },
  ];

  it("returns markers within window", () => {
    const slice = projectMarkersInWindow({ markers, startNs: 200, endNs: 800 });
    expect(slice.map((m) => m.id)).toEqual(["b"]);
  });

  it("returns all markers when no window is supplied", () => {
    const slice = projectMarkersInWindow({ markers });
    expect(slice).toHaveLength(3);
  });

  it("respects the limit cap", () => {
    const slice = projectMarkersInWindow({ markers, limit: 2 });
    expect(slice).toHaveLength(2);
  });
});

describe("describeMarker", () => {
  it("joins kind + detail when detail is present", () => {
    const desc = describeMarker({
      id: "a",
      queueId: "q-1",
      kind: "saturation",
      severity: "saturated",
      monotonicNs: 0,
      label: "Saturated",
      detail: "size=10/10",
    });
    expect(desc).toBe("Saturation: size=10/10");
  });

  it("uses the kind label when no detail is present", () => {
    const desc = describeMarker({
      id: "a",
      queueId: "q-1",
      kind: "pressure-change",
      severity: "warning",
      monotonicNs: 0,
      label: "calm → warning",
    });
    expect(desc).toBe("Pressure change");
  });
});
