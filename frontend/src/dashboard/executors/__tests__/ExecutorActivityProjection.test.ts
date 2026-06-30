import { describe, expect, it } from "vitest";
import {
  describeMarker,
  projectMarkersInWindow,
  projectRecord,
  projectExecutorActivity,
} from "@/dashboard/executors/ExecutorActivityProjection";
import type { ExecutorActivityMarker } from "@/dashboard/executors/models/ExecutorActivityModels";
import { makeRecord } from "@/dashboard/executors/__fixtures__/executorActivityFixtures";

describe("projectRecord", () => {
  it("derives calm for an idle executor", () => {
    const view = projectRecord(makeRecord());
    expect(view.severity).toBe("calm");
  });

  it("escalates to saturated when fully utilized + backlog > 0", () => {
    const view = projectRecord(
      makeRecord({
        utilization: {
          ...makeRecord().utilization,
          active_workers: 4,
          utilization_ratio: 1.0,
        },
        throughput: { ...makeRecord().throughput, backlog: 3 },
      }),
    );
    expect(view.severity).toBe("saturated");
    expect(view.saturated).toBe(true);
  });

  it("inherits warning + critical levels from the backend", () => {
    const warn = projectRecord(
      makeRecord({
        saturation: { ...makeRecord().saturation, level: "warning" },
      }),
    );
    expect(warn.severity).toBe("warning");
    const crit = projectRecord(
      makeRecord({
        saturation: { ...makeRecord().saturation, level: "critical" },
      }),
    );
    expect(crit.severity).toBe("critical");
  });

  it("falls back to executor id for display name", () => {
    expect(projectRecord(makeRecord({ executor_id: "e-99" })).displayName).toBe("e-99");
    expect(projectRecord(makeRecord({ executor_id: "e-99" }), "thread-pool").displayName).toBe(
      "thread-pool",
    );
  });
});

describe("projectExecutorActivity", () => {
  it("sorts by severity descending, then saturation score", () => {
    const records = [
      makeRecord({ executor_id: "e-calm" }),
      makeRecord({
        executor_id: "e-warn",
        saturation: {
          ...makeRecord().saturation,
          level: "warning",
          saturation_score: 0.72,
        },
      }),
      makeRecord({
        executor_id: "e-sat",
        utilization: {
          ...makeRecord().utilization,
          active_workers: 4,
          utilization_ratio: 1.0,
        },
        throughput: { ...makeRecord().throughput, backlog: 2 },
        saturation: {
          ...makeRecord().saturation,
          level: "critical",
          saturation_score: 0.95,
        },
      }),
    ];
    const { bySeverityDescending, alarmCount } = projectExecutorActivity({ records });
    expect(bySeverityDescending.map((v) => v.executorId)).toEqual(["e-sat", "e-warn", "e-calm"]);
    expect(alarmCount).toBe(2);
  });

  it("returns empty projection for empty input", () => {
    const projection = projectExecutorActivity({ records: [] });
    expect(projection.views).toEqual([]);
    expect(projection.alarmCount).toBe(0);
  });
});

describe("projectMarkersInWindow", () => {
  const markers: ExecutorActivityMarker[] = [
    {
      id: "a",
      executorId: "e-1",
      kind: "saturation-changed",
      severity: "warning",
      monotonicNs: 100,
      label: "a",
    },
    {
      id: "b",
      executorId: "e-1",
      kind: "contention",
      severity: "warning",
      monotonicNs: 500,
      label: "b",
    },
    {
      id: "c",
      executorId: "e-2",
      kind: "latency-spike",
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
  it("joins kind + detail when detail is present", () => {
    expect(
      describeMarker({
        id: "a",
        executorId: "e-1",
        kind: "latency-spike",
        severity: "warning",
        monotonicNs: 0,
        label: "500ms wait",
        detail: "threshold=250ms",
      }),
    ).toBe("Latency spike: threshold=250ms");
  });
});
