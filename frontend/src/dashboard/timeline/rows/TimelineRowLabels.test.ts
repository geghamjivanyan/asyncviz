import { describe, expect, it } from "vitest";
import {
  TimelineRowLabelRenderer,
  truncateText,
} from "@/dashboard/timeline/rows/TimelineRowLabels";
import { TimelineRowTextCache } from "@/dashboard/timeline/rows/TimelineRowCaching";
import { TimelineRowMetrics } from "@/dashboard/timeline/rows/TimelineRowMetrics";
import { DEFAULT_TIMELINE_PALETTE } from "@/dashboard/timeline/rendering/TimelineColors";
import { makeRowLayout } from "@/dashboard/timeline/rows/TimelineRowLayout";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { normalizeRow } from "@/dashboard/timeline/rows/utils/normalizeRow";
import { createRowFakeContext } from "@/dashboard/timeline/rows/__fixtures__/mockCanvas";

function buildLayout() {
  const layout = makeRowLayout({
    rowHeightPx: 28,
    labelColumnWidthPx: 200,
    indentPerDepthPx: 8,
  });
  const coords = new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 28 },
    { cssWidth: 800, cssHeight: 200, devicePixelRatio: 1 },
  );
  return layout.resolve(coords);
}

describe("truncateText", () => {
  it("returns the original string when it fits", () => {
    const ctx = createRowFakeContext() as unknown as CanvasRenderingContext2D;
    const { text, truncated } = truncateText(ctx, "12px sans", "abcd", 400);
    expect(text).toBe("abcd");
    expect(truncated).toBe(false);
  });

  it("trims with an ellipsis when the string overflows", () => {
    const ctx = createRowFakeContext() as unknown as CanvasRenderingContext2D;
    const { text, truncated } = truncateText(ctx, "12px sans", "abcdefghij", 24);
    expect(text.endsWith("…")).toBe(true);
    expect(truncated).toBe(true);
  });

  it("returns ellipsis-only when no characters fit", () => {
    const ctx = createRowFakeContext() as unknown as CanvasRenderingContext2D;
    const { text, truncated } = truncateText(ctx, "12px sans", "abc", 4);
    expect(text).toBe("…");
    expect(truncated).toBe(true);
  });
});

describe("TimelineRowLabelRenderer", () => {
  it("hits the text cache on the second render", () => {
    const cache = new TimelineRowTextCache();
    const metrics = new TimelineRowMetrics();
    const renderer = new TimelineRowLabelRenderer({ cache, metrics });
    const ctx = createRowFakeContext() as unknown as CanvasRenderingContext2D;
    const layout = buildLayout();
    const row = normalizeRow({
      rowIndex: 0,
      taskId: "t1",
      label: "Hello world that is fairly long for truncation",
      coroutineName: "fn",
      state: "running",
    });
    renderer.render({ ctx, palette: DEFAULT_TIMELINE_PALETTE, layout, row, rowTopY: 0 });
    renderer.render({ ctx, palette: DEFAULT_TIMELINE_PALETTE, layout, row, rowTopY: 0 });
    const stats = renderer.cacheStats();
    expect(stats.hits).toBeGreaterThan(0);
    const snap = metrics.snapshot();
    expect(snap.labelsRendered).toBe(2);
    expect(snap.textCacheHits).toBeGreaterThan(0);
  });

  it("reports truncation through the metrics sink", () => {
    const metrics = new TimelineRowMetrics();
    const renderer = new TimelineRowLabelRenderer({ metrics });
    const ctx = createRowFakeContext() as unknown as CanvasRenderingContext2D;
    const layout = buildLayout();
    const row = normalizeRow({
      rowIndex: 0,
      taskId: "t1",
      label: "Very-long-label-that-cannot-possibly-fit-in-the-narrow-column",
      state: "running",
    });
    renderer.render({ ctx, palette: DEFAULT_TIMELINE_PALETTE, layout, row, rowTopY: 0 });
    expect(metrics.snapshot().labelsTruncated).toBe(1);
  });
});
