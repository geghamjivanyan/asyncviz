import { describe, expect, it } from "vitest";
import {
  applyFilter,
  bucketViews,
  compareViews,
  filterFromMode,
  groupFromEventPayload,
  intentFor,
  projectGroup,
  summarize,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";
import {
  makeEvent,
  makeGroup,
} from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

describe("intentFor", () => {
  it("maps terminal states to 'resolved' regardless of severity", () => {
    expect(intentFor("FREEZE", "recovered")).toBe("resolved");
    expect(intentFor("CRITICAL", "expired")).toBe("resolved");
  });
  it("maps severity to intent for open states", () => {
    expect(intentFor("FREEZE", "active")).toBe("freeze");
    expect(intentFor("CRITICAL", "active")).toBe("critical");
    expect(intentFor("WARNING", "active")).toBe("warning");
    expect(intentFor("NONE", "active")).toBe("info");
  });
});

describe("projectGroup", () => {
  it("includes derived fields (intent, ms durations, labels)", () => {
    const group = makeGroup();
    const view = projectGroup(group);
    expect(view.isOpen).toBe(true);
    expect(view.intent).toBe("critical");
    expect(view.freezeDurationMs).toBeGreaterThan(0);
    expect(view.peakLagMs).toBe(800);
    expect(view.stateLabel).toBe("Active");
    expect(view.severityLabel).toBe("Critical");
  });

  it("derives ms duration from ns when ms field is missing", () => {
    const group = makeGroup({ freeze_duration_ms: undefined });
    const view = projectGroup(group);
    expect(view.freezeDurationMs).toBeCloseTo(1_500);
  });
});

describe("groupFromEventPayload", () => {
  it("round-trips through projectGroup with identical group_id", () => {
    const event = makeEvent();
    const view = projectGroup(groupFromEventPayload(event));
    expect(view.groupId).toBe(event.group_id);
    expect(view.severity).toBe(event.severity);
  });
});

describe("compareViews", () => {
  it("orders open before terminal", () => {
    const open = projectGroup(makeGroup({ group_id: "a", state: "active" }));
    const recovered = projectGroup(makeGroup({ group_id: "b", state: "recovered" }));
    expect(compareViews(open, recovered)).toBeLessThan(0);
  });

  it("orders by severity rank within a bucket", () => {
    const critical = projectGroup(
      makeGroup({ group_id: "a", severity: "CRITICAL" }),
    );
    const freeze = projectGroup(
      makeGroup({ group_id: "b", severity: "FREEZE" }),
    );
    expect(compareViews(freeze, critical)).toBeLessThan(0);
  });
});

describe("filtering", () => {
  it("filterFromMode returns severity set for freeze-only", () => {
    const f = filterFromMode("freeze-only");
    expect(f.severities?.has("FREEZE")).toBe(true);
    expect(f.severities?.has("CRITICAL")).toBe(false);
  });

  it("applyFilter respects activeOnly", () => {
    const open = projectGroup(makeGroup({ group_id: "a", state: "active" }));
    const recovered = projectGroup(
      makeGroup({ group_id: "b", state: "recovered" }),
    );
    const result = applyFilter([open, recovered], filterFromMode("active"));
    expect(result.map((v) => v.groupId)).toEqual(["a"]);
  });

  it("applyFilter respects minFreezeMs", () => {
    const tiny = projectGroup(
      makeGroup({
        group_id: "small",
        freeze_duration_ns: 100_000,
        freeze_duration_ms: 0.1,
      }),
    );
    const big = projectGroup(
      makeGroup({
        group_id: "big",
        freeze_duration_ns: 2_000_000_000,
        freeze_duration_ms: 2_000,
      }),
    );
    const result = applyFilter([tiny, big], {
      severities: null,
      activeOnly: false,
      terminalOnly: false,
      minFreezeMs: 100,
    });
    expect(result.map((v) => v.groupId)).toEqual(["big"]);
  });
});

describe("bucketViews + summarize", () => {
  it("buckets open vs terminal and sorts each bucket", () => {
    const a = projectGroup(makeGroup({ group_id: "a", state: "active", severity: "WARNING" }));
    const b = projectGroup(makeGroup({ group_id: "b", state: "active", severity: "FREEZE" }));
    const c = projectGroup(makeGroup({ group_id: "c", state: "recovered" }));
    const buckets = bucketViews([a, b, c]);
    expect(buckets.active.map((v) => v.groupId)).toEqual(["b", "a"]);
    expect(buckets.recent.map((v) => v.groupId)).toEqual(["c"]);
  });

  it("summarize counts by severity + lifecycle", () => {
    const views = [
      projectGroup(makeGroup({ group_id: "a", severity: "FREEZE", state: "active" })),
      projectGroup(makeGroup({ group_id: "b", severity: "CRITICAL", state: "recovered" })),
    ];
    const counts = summarize(views);
    expect(counts.total).toBe(2);
    expect(counts.active).toBe(1);
    expect(counts.recovered).toBe(1);
    expect(counts.bySeverity.FREEZE).toBe(1);
    expect(counts.bySeverity.CRITICAL).toBe(1);
  });
});
