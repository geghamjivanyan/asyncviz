import { describe, expect, it } from "vitest";
import {
  projectFreezeRegion,
  projectFreezeRegions,
} from "@/dashboard/timeline/freeze_regions/selectors/projectFreezeRegions";
import { makeGroup } from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

const NS_PER_S = 1e9;

describe("projectFreezeRegion", () => {
  it("converts ns timestamps to seconds for canvas-side rendering", () => {
    const group = makeGroup({
      first_seen_ns: 1_500_000_000,
      last_seen_ns: 3_500_000_000,
    });
    const region = projectFreezeRegion(group)!;
    expect(region.startSeconds).toBeCloseTo(1.5);
    expect(region.endSeconds).toBeCloseTo(3.5);
    expect(region.durationSeconds).toBeCloseTo(2.0);
  });

  it("uses recovered_ns as the end-time when terminal", () => {
    const group = makeGroup({
      state: "recovered",
      first_seen_ns: 1 * NS_PER_S,
      last_seen_ns: 2 * NS_PER_S,
      recovered_ns: 2.4 * NS_PER_S,
    });
    const region = projectFreezeRegion(group)!;
    expect(region.endSeconds).toBeCloseTo(2.4);
  });

  it("falls back to expired_ns when recovered_ns is missing", () => {
    const group = makeGroup({
      state: "expired",
      recovered_ns: null,
      expired_ns: 5 * NS_PER_S,
      last_seen_ns: 4 * NS_PER_S,
    });
    const region = projectFreezeRegion(group)!;
    expect(region.endSeconds).toBeCloseTo(5.0);
  });

  it("falls back to last_seen_ns when neither close-out instant exists", () => {
    const group = makeGroup({
      state: "recovered",
      recovered_ns: null,
      expired_ns: null,
      last_seen_ns: 6 * NS_PER_S,
    });
    const region = projectFreezeRegion(group)!;
    expect(region.endSeconds).toBeCloseTo(6.0);
  });

  it("returns null for groups with no severity contribution", () => {
    const group = makeGroup({ severity: "NONE", peak_severity: "NONE" });
    expect(projectFreezeRegion(group)).toBeNull();
  });

  it("propagates capture + escalation counts", () => {
    const group = makeGroup({ capture_ids: [1, 2, 3, 4], escalation_count: 2 });
    const region = projectFreezeRegion(group)!;
    expect(region.captureCount).toBe(4);
    expect(region.escalationCount).toBe(2);
  });

  it("maps emitter state to lifecycle bucket", () => {
    expect(projectFreezeRegion(makeGroup({ state: "active" }))!.lifecycle).toBe("active");
    expect(projectFreezeRegion(makeGroup({ state: "recovered" }))!.lifecycle).toBe(
      "recovered",
    );
  });
});

describe("projectFreezeRegions", () => {
  it("sorts active > recovered, then by severity desc", () => {
    const groupsById = {
      a: makeGroup({
        group_id: "a",
        state: "recovered",
        severity: "FREEZE",
        peak_severity: "FREEZE",
        recovered_ns: 5 * NS_PER_S,
      }),
      b: makeGroup({
        group_id: "b",
        state: "active",
        severity: "WARNING",
        peak_severity: "WARNING",
      }),
      c: makeGroup({
        group_id: "c",
        state: "active",
        severity: "FREEZE",
        peak_severity: "FREEZE",
      }),
    };
    const ordered = projectFreezeRegions(groupsById).map((r) => r.groupId);
    expect(ordered).toEqual(["c", "b", "a"]);
  });

  it("returns an empty array for an empty store slice", () => {
    expect(projectFreezeRegions({})).toEqual([]);
  });
});
