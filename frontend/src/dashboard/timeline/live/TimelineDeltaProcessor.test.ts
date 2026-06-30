import { describe, expect, it } from "vitest";
import { TimelineDeltaProcessor } from "@/dashboard/timeline/live/TimelineDeltaProcessor";
import { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";
import {
  makeHeartbeatEnvelope,
  makeRuntimeEventEnvelope,
  makeTimelineDeltaEnvelope,
  makeWarningDeltaEnvelope,
} from "@/dashboard/timeline/live/__fixtures__/mockEnvelopes";

describe("TimelineDeltaProcessor", () => {
  it("emits a segment-scope invalidation for timeline_delta with a segment id", () => {
    const proc = new TimelineDeltaProcessor();
    const tracker = new TimelineInvalidationTracker();
    const envelope = makeTimelineDeltaEnvelope({
      sequence: 1,
      taskId: "t1",
      kind: "segment_opened",
      segmentId: "seg-1",
    });
    const result = proc.process(envelope, tracker);
    expect(result.invalidated).toBe(true);
    const batch = tracker.drain();
    expect(batch.segmentIds).toEqual(["seg-1"]);
    expect(batch.taskIds).toEqual(["t1"]);
  });

  it("falls back to row-scope invalidation for span_finalized", () => {
    const proc = new TimelineDeltaProcessor();
    const tracker = new TimelineInvalidationTracker();
    proc.process(
      makeTimelineDeltaEnvelope({
        sequence: 1,
        taskId: "t1",
        kind: "span_finalized",
      }),
      tracker,
    );
    const batch = tracker.drain();
    expect(batch.taskIds).toEqual(["t1"]);
    expect(batch.reasons).toContain("row");
  });

  it("emits row + warning invalidations for warning_delta", () => {
    const proc = new TimelineDeltaProcessor();
    const tracker = new TimelineInvalidationTracker();
    proc.process(
      makeWarningDeltaEnvelope({ sequence: 1, warningId: "w1", taskIds: ["a", "b"] }),
      tracker,
    );
    const batch = tracker.drain();
    expect(batch.reasons).toContain("warning");
    expect(batch.reasons).toContain("row");
    expect([...batch.taskIds].sort()).toEqual(["a", "b"]);
  });

  it("emits a row invalidation for runtime_event", () => {
    const proc = new TimelineDeltaProcessor();
    const tracker = new TimelineInvalidationTracker();
    proc.process(makeRuntimeEventEnvelope(1, "t1"), tracker);
    const batch = tracker.drain();
    expect(batch.taskIds).toEqual(["t1"]);
  });

  it("no-ops heartbeat envelopes without pushing regions", () => {
    const proc = new TimelineDeltaProcessor();
    const tracker = new TimelineInvalidationTracker();
    const result = proc.process(makeHeartbeatEnvelope(), tracker);
    expect(result.invalidated).toBe(false);
    expect(tracker.isDirty()).toBe(false);
  });

  it("suppresses envelopes whose sequence is at or before lastAppliedSequence", () => {
    const proc = new TimelineDeltaProcessor();
    const tracker = new TimelineInvalidationTracker();
    const result = proc.process(makeRuntimeEventEnvelope(5, "t1"), tracker, {
      lastAppliedSequence: 10,
    });
    expect(result.suppressed).toBe(true);
    expect(result.suppressionReason).toBe("stale");
    expect(tracker.isDirty()).toBe(false);
  });

  it("counts processed + suppressed envelopes", () => {
    const proc = new TimelineDeltaProcessor();
    const tracker = new TimelineInvalidationTracker();
    proc.process(makeRuntimeEventEnvelope(1, "t1"), tracker);
    proc.process(makeRuntimeEventEnvelope(2, "t2"), tracker);
    proc.process(makeRuntimeEventEnvelope(1, "t1"), tracker, { lastAppliedSequence: 5 });
    const snap = proc.metrics();
    expect(snap.processed).toBe(2);
    expect(snap.suppressed).toBe(1);
  });
});
