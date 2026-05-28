import { describe, expect, it } from "vitest";
import { TimelineViewportWindow } from "@/dashboard/timeline/virtualization/TimelineViewportWindow";
import { buildCoords } from "@/dashboard/timeline/virtualization/__fixtures__/makeFixtures";

describe("TimelineViewportWindow", () => {
  it("resolves a strict + overscan window", () => {
    const w = new TimelineViewportWindow({ overscan: { rowOverscan: 2, timeOverscanSeconds: 1 } });
    const snapshot = w.resolve(buildCoords({ rowStart: 5, cssHeight: 100, rowHeight: 20 }), 100, 1);
    expect(snapshot.rows.startIndex).toBe(5);
    expect(snapshot.rows.endIndex).toBeGreaterThan(5);
    expect(snapshot.rows.overscanStartIndex).toBeLessThanOrEqual(snapshot.rows.startIndex);
    expect(snapshot.rows.overscanEndIndex).toBeGreaterThanOrEqual(snapshot.rows.endIndex);
    expect(snapshot.time.startSeconds).toBe(0);
    expect(snapshot.time.endSeconds).toBe(10);
    expect(snapshot.time.overscanStartSeconds).toBe(-1);
    expect(snapshot.time.overscanEndSeconds).toBe(11);
  });

  it("returns the same snapshot reference for identical inputs", () => {
    const w = new TimelineViewportWindow();
    const coords = buildCoords({});
    const a = w.resolve(coords, 50, 1);
    const b = w.resolve(coords, 50, 1);
    expect(a).toBe(b);
  });

  it("rebuilds when the sequence advances", () => {
    const w = new TimelineViewportWindow();
    const coords = buildCoords({});
    const a = w.resolve(coords, 50, 1);
    const b = w.resolve(coords, 50, 2);
    expect(a).not.toBe(b);
  });

  it("rebuilds when overscan changes", () => {
    const w = new TimelineViewportWindow({ overscan: { rowOverscan: 1 } });
    const coords = buildCoords({});
    const a = w.resolve(coords, 50, 1);
    w.setOverscan({ rowOverscan: 5 });
    const b = w.resolve(coords, 50, 1);
    expect(a).not.toBe(b);
    expect(b.rows.overscanStartIndex).toBeLessThanOrEqual(a.rows.overscanStartIndex);
  });

  it("clamps overscan at row boundaries", () => {
    const w = new TimelineViewportWindow({ overscan: { rowOverscan: 100 } });
    const snapshot = w.resolve(buildCoords({ rowStart: 0, cssHeight: 40, rowHeight: 20 }), 5, 1);
    expect(snapshot.rows.overscanStartIndex).toBe(0);
    expect(snapshot.rows.overscanEndIndex).toBe(5);
  });

  it("tracks resolutions + hits in metrics", () => {
    const w = new TimelineViewportWindow();
    const coords = buildCoords({});
    w.resolve(coords, 10, 1);
    w.resolve(coords, 10, 1);
    w.resolve(coords, 10, 1);
    const m = w.metrics();
    expect(m.resolutions).toBe(3);
    expect(m.hits).toBe(2);
  });
});
