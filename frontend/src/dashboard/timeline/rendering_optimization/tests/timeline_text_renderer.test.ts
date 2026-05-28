import { describe, expect, it, vi } from "vitest";
import { TimelineTextRenderer, type TextMeasurer } from "../timeline_text_renderer";

function fakeMeasurer(callCounter: { calls: number }): TextMeasurer {
  return {
    measure(_font, text) {
      callCounter.calls += 1;
      return {
        width: text.length * 7,
        actualBoundingBoxAscent: 8,
        actualBoundingBoxDescent: 2,
      };
    },
  };
}

describe("TimelineTextRenderer", () => {
  it("caches measurements by font + text", () => {
    const counter = { calls: 0 };
    const r = new TimelineTextRenderer(16);
    const m = fakeMeasurer(counter);
    r.measure(m, "12px sans", "hello");
    r.measure(m, "12px sans", "hello");
    expect(counter.calls).toBe(1);
  });

  it("treats different fonts as distinct entries", () => {
    const counter = { calls: 0 };
    const r = new TimelineTextRenderer(16);
    const m = fakeMeasurer(counter);
    r.measure(m, "12px sans", "hello");
    r.measure(m, "13px sans", "hello");
    expect(counter.calls).toBe(2);
  });

  it("returns dimensions from the measurer", () => {
    const r = new TimelineTextRenderer(16);
    const m = fakeMeasurer({ calls: 0 });
    const out = r.measure(m, "12px sans", "abc");
    expect(out.width).toBe(21);
    expect(out.actualAscent).toBe(8);
    expect(out.actualDescent).toBe(2);
  });

  it("reports stats including hit/miss + measure requests", () => {
    const r = new TimelineTextRenderer(16);
    const m = fakeMeasurer({ calls: 0 });
    r.measure(m, "12px sans", "a");
    r.measure(m, "12px sans", "a");
    r.measure(m, "12px sans", "b");
    const s = r.stats();
    expect(s.measureRequests).toBe(3);
    expect(s.measureMisses).toBe(2);
    expect(s.hits).toBe(1);
  });

  it("never calls the measurer twice for the same key", () => {
    const r = new TimelineTextRenderer(16);
    const m = { measure: vi.fn(() => ({ width: 10 })) };
    r.measure(m, "f", "x");
    r.measure(m, "f", "x");
    expect(m.measure).toHaveBeenCalledTimes(1);
  });

  it("falls back to 0 for non-finite widths", () => {
    const r = new TimelineTextRenderer(16);
    const m = { measure: () => ({ width: Number.NaN }) };
    const out = r.measure(m, "f", "x");
    expect(out.width).toBe(0);
  });
});
