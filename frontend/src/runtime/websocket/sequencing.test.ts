import { describe, expect, it } from "vitest";
import { SequenceTracker } from "@/runtime/websocket/sequencing";

describe("SequenceTracker.decide", () => {
  it("accepts strictly-greater sequences", () => {
    const tracker = new SequenceTracker(5);
    expect(tracker.decide(6)).toBe("accept");
  });

  it("flags equal sequences as duplicates", () => {
    const tracker = new SequenceTracker(5);
    expect(tracker.decide(5)).toBe("duplicate");
  });

  it("flags lower sequences as stale", () => {
    const tracker = new SequenceTracker(5);
    expect(tracker.decide(4)).toBe("stale");
  });

  it("detects out-of-order gaps", () => {
    const tracker = new SequenceTracker(5);
    expect(tracker.decide(10)).toBe("out-of-order");
  });

  it("accepts null/undefined sequences (unsequenced channel)", () => {
    const tracker = new SequenceTracker(5);
    expect(tracker.decide(null)).toBe("accept");
    expect(tracker.decide(undefined)).toBe("accept");
  });

  it("commit() advances the cursor on accept", () => {
    const tracker = new SequenceTracker(5);
    tracker.commit(6);
    expect(tracker.lastSequence).toBe(6);
  });

  it("commit() does not advance on null sequence", () => {
    const tracker = new SequenceTracker(5);
    tracker.commit(null);
    expect(tracker.lastSequence).toBe(5);
  });

  it("resnap() resets the cursor when allowBackwardSnapshot is true", () => {
    const tracker = new SequenceTracker(100);
    tracker.resnap(50);
    expect(tracker.lastSequence).toBe(50);
  });

  it("resnap() does not regress when allowBackwardSnapshot is false", () => {
    const tracker = new SequenceTracker(100, { allowBackwardSnapshot: false });
    tracker.resnap(50);
    expect(tracker.lastSequence).toBe(100);
    tracker.resnap(150);
    expect(tracker.lastSequence).toBe(150);
  });

  it("snapshot() reports per-decision counters", () => {
    const tracker = new SequenceTracker(0);
    tracker.commit(1);
    tracker.commit(2);
    tracker.recordDuplicate();
    tracker.recordStale();
    tracker.recordOutOfOrder();
    const snap = tracker.snapshot();
    expect(snap.lastSequence).toBe(2);
    expect(snap.accepted).toBe(2);
    expect(snap.duplicate).toBe(1);
    expect(snap.stale).toBe(1);
    expect(snap.outOfOrder).toBe(1);
  });

  it("reset() returns the tracker to a fresh state", () => {
    const tracker = new SequenceTracker(0);
    tracker.commit(5);
    tracker.recordDuplicate();
    tracker.reset(0);
    expect(tracker.snapshot()).toEqual({
      lastSequence: 0,
      accepted: 0,
      duplicate: 0,
      stale: 0,
      outOfOrder: 0,
    });
  });
});
