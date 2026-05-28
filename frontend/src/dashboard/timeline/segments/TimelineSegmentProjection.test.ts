import { describe, expect, it } from "vitest";
import { projectTimelineSegments } from "@/dashboard/timeline/segments/TimelineSegmentProjection";
import { EMPTY_TIMELINE_SEGMENT_PROJECTION } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";
import { makeTask, makeWarning } from "@/dashboard/timeline/rows/__fixtures__/makeTask";
import {
  makeActiveWireSegment,
  makeWireSegment,
} from "@/dashboard/timeline/segments/__fixtures__/makeSegment";

describe("projectTimelineSegments", () => {
  it("returns the empty projection when there are no tasks", () => {
    expect(
      projectTimelineSegments({
        tasksById: {},
        segmentsById: {},
        segmentIdsByTaskId: {},
        activeSegmentsByTaskId: {},
      }),
    ).toBe(EMPTY_TIMELINE_SEGMENT_PROJECTION);
  });

  it("orders entries deterministically by (rowIndex, startSeconds, id)", () => {
    const projection = projectTimelineSegments({
      tasksById: {
        a: makeTask("a", { created_at: 0 }),
        b: makeTask("b", { created_at: 1 }),
      },
      segmentsById: {
        s_b_late: makeWireSegment("s_b_late", "b", 3_000_000_000, 5_000_000_000),
        s_b_early: makeWireSegment("s_b_early", "b", 1_000_000_000, 2_000_000_000),
        s_a_first: makeWireSegment("s_a_first", "a", 1_000_000_000, 2_000_000_000),
      },
      segmentIdsByTaskId: { a: ["s_a_first"], b: ["s_b_late", "s_b_early"] },
      activeSegmentsByTaskId: {},
    });
    expect(projection.segments.map((s) => s.segmentId)).toEqual([
      "s_a_first",
      "s_b_early",
      "s_b_late",
    ]);
  });

  it("tags closed segments with the terminal task lifecycle when applicable", () => {
    const projection = projectTimelineSegments({
      tasksById: {
        ok: makeTask("ok", { state: "completed" }),
        fail: makeTask("fail", { state: "failed", created_at: 1 }),
      },
      segmentsById: {
        s_ok: makeWireSegment("s_ok", "ok", 0, 1_000_000_000),
        s_fail: makeWireSegment("s_fail", "fail", 0, 1_000_000_000),
      },
      segmentIdsByTaskId: { ok: ["s_ok"], fail: ["s_fail"] },
      activeSegmentsByTaskId: {},
    });
    const ok = projection.segments.find((s) => s.taskId === "ok")!;
    const fail = projection.segments.find((s) => s.taskId === "fail")!;
    expect(ok.lifecycleState).toBe("completed");
    expect(fail.lifecycleState).toBe("failed");
  });

  it("marks active segments without overriding their lifecycle", () => {
    const projection = projectTimelineSegments({
      tasksById: { t1: makeTask("t1") },
      segmentsById: {},
      segmentIdsByTaskId: {},
      activeSegmentsByTaskId: {
        t1: makeActiveWireSegment("a1", "t1", 5_000_000_000, { segment_type: "wait" }),
      },
    });
    expect(projection.hasActiveSegments).toBe(true);
    expect(projection.segments[0]!.isActive).toBe(true);
    expect(projection.segments[0]!.lifecycleState).toBe("waiting");
  });

  it("propagates warning severity from active warnings", () => {
    const projection = projectTimelineSegments({
      tasksById: { t1: makeTask("t1") },
      segmentsById: { s: makeWireSegment("s", "t1", 0, 1_000_000_000) },
      segmentIdsByTaskId: { t1: ["s"] },
      activeSegmentsByTaskId: {},
      activeWarnings: [
        makeWarning("w1", ["t1"], "warning"),
        makeWarning("w2", ["t1"], "critical"),
      ],
    });
    expect(projection.segments[0]!.warningSeverity).toBe("critical");
  });

  it("attaches replay marks only to the focused segment / task", () => {
    const projection = projectTimelineSegments({
      tasksById: { t1: makeTask("t1"), t2: makeTask("t2", { created_at: 1 }) },
      segmentsById: {
        s1: makeWireSegment("s1", "t1", 0, 1_000_000_000),
        s2: makeWireSegment("s2", "t2", 0, 1_000_000_000),
      },
      segmentIdsByTaskId: { t1: ["s1"], t2: ["s2"] },
      activeSegmentsByTaskId: {},
      replay: { sequence: 99, focusedSegmentId: "s2" },
    });
    expect(projection.segments.find((s) => s.segmentId === "s1")!.replay).toBeNull();
    expect(projection.segments.find((s) => s.segmentId === "s2")!.replay).toEqual({
      sequence: 99,
      focused: true,
      finalizedBeforeCursor: true,
    });
  });

  it("builds O(1) lookup indices by segment id + task id", () => {
    const projection = projectTimelineSegments({
      tasksById: { t1: makeTask("t1") },
      segmentsById: {
        s1: makeWireSegment("s1", "t1", 0, 1_000_000_000),
        s2: makeWireSegment("s2", "t1", 1_000_000_000, 2_000_000_000),
      },
      segmentIdsByTaskId: { t1: ["s2", "s1"] },
      activeSegmentsByTaskId: {},
    });
    expect(projection.indexBySegmentId.get("s1")).toBe(0);
    expect(projection.indexBySegmentId.get("s2")).toBe(1);
    expect(projection.indicesByTaskId.get("t1")).toEqual([0, 1]);
  });

  it("is replay-safe — identical inputs produce identical projections", () => {
    const inputs = {
      tasksById: { t1: makeTask("t1") },
      segmentsById: { s: makeWireSegment("s", "t1", 0, 1_000_000_000) },
      segmentIdsByTaskId: { t1: ["s"] },
      activeSegmentsByTaskId: {},
      sequence: 7,
    };
    const a = projectTimelineSegments(inputs);
    const b = projectTimelineSegments(inputs);
    expect(a.segments).toEqual(b.segments);
    expect(a.sequence).toBe(b.sequence);
  });
});
