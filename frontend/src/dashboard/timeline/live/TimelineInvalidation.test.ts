import { describe, expect, it } from "vitest";
import { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";
import {
  invalidateRow,
  invalidateRows,
} from "@/dashboard/timeline/live/TimelineRowInvalidation";
import {
  invalidateSegment,
  invalidateSegments,
} from "@/dashboard/timeline/live/TimelineSegmentInvalidation";
import {
  invalidateSelection,
  invalidateViewport,
  invalidateWarnings,
} from "@/dashboard/timeline/live/TimelineViewportInvalidation";

describe("TimelineInvalidationTracker", () => {
  it("starts clean and reports no dirty state", () => {
    const tracker = new TimelineInvalidationTracker();
    expect(tracker.isDirty()).toBe(false);
    expect(tracker.size()).toBe(0);
    expect(tracker.peek().regionCount).toBe(0);
  });

  it("accumulates regions and exposes them through drain()", () => {
    const tracker = new TimelineInvalidationTracker();
    invalidateRow(tracker, "task-1", { sequence: 10 });
    invalidateSegment(tracker, "seg-1", "task-1", { sequence: 11 });
    expect(tracker.isDirty()).toBe(true);
    const batch = tracker.drain();
    expect(batch.regionCount).toBe(2);
    expect(batch.taskIds).toEqual(["task-1"]);
    expect(batch.segmentIds).toEqual(["seg-1"]);
    expect(batch.highestSequence).toBe(11);
    expect(tracker.isDirty()).toBe(false);
  });

  it("coalesces multiple row + segment invalidations", () => {
    const tracker = new TimelineInvalidationTracker();
    invalidateRows(tracker, ["a", "b"]);
    invalidateSegments(tracker, ["s1", "s2"], ["a"]);
    const batch = tracker.drain();
    expect([...batch.taskIds].sort()).toEqual(["a", "b"]);
    expect([...batch.segmentIds].sort()).toEqual(["s1", "s2"]);
  });

  it("flags viewport + selection invalidations on the batch", () => {
    const tracker = new TimelineInvalidationTracker();
    invalidateViewport(tracker);
    invalidateSelection(tracker);
    invalidateWarnings(tracker, ["t1"]);
    const batch = tracker.drain();
    expect(batch.includesViewport).toBe(true);
    expect([...batch.reasons].sort()).toEqual(["selection", "viewport", "warning"].sort());
  });

  it("clear() resets without producing a batch", () => {
    const tracker = new TimelineInvalidationTracker();
    invalidateRow(tracker, "t1");
    tracker.clear();
    expect(tracker.isDirty()).toBe(false);
    expect(tracker.size()).toBe(0);
  });

  it("tracks total pushed + drained counters", () => {
    const tracker = new TimelineInvalidationTracker();
    invalidateRow(tracker, "a");
    invalidateRow(tracker, "b");
    tracker.drain();
    expect(tracker.totalPushed()).toBe(2);
    expect(tracker.totalDrained()).toBe(1);
  });
});
