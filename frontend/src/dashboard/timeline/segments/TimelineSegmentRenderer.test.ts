import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { TimelineSegmentRenderer } from "@/dashboard/timeline/segments/TimelineSegmentRenderer";
import { TimelineSegmentMetrics } from "@/dashboard/timeline/segments/TimelineSegmentMetrics";
import { DEFAULT_TIMELINE_PALETTE } from "@/dashboard/timeline/rendering/TimelineColors";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { RenderContext } from "@/dashboard/timeline/rendering/TimelineLayer";
import {
  createRowFakeContext,
  installRowFakeCanvasContext,
} from "@/dashboard/timeline/rows/__fixtures__/mockCanvas";
import { makeRenderSegment } from "@/dashboard/timeline/segments/__fixtures__/makeSegment";
import { makeRowLayout } from "@/dashboard/timeline/rows/TimelineRowLayout";

let restoreCanvas: (() => void) | undefined;
beforeAll(() => {
  restoreCanvas = installRowFakeCanvasContext();
});
afterAll(() => {
  restoreCanvas?.();
});

function buildContext({
  rows = 2,
  segments,
  selectedTaskId = null,
  cssWidth = 800,
  devicePixelRatio = 2,
}: {
  rows?: number;
  segments?: ReturnType<typeof makeRenderSegment>[];
  selectedTaskId?: string | null;
  cssWidth?: number;
  devicePixelRatio?: number;
}) {
  const coords = new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 22 },
    { cssWidth, cssHeight: 240, devicePixelRatio },
  );
  const ctx = createRowFakeContext() as unknown as CanvasRenderingContext2D;
  const renderContext: RenderContext = {
    ctx,
    coords,
    palette: DEFAULT_TIMELINE_PALETTE,
    scene: {
      totalRows: rows,
      rows: [],
      segments: segments ?? [
        makeRenderSegment("s1", 0, 1, 3, { lifecycleState: "running" }),
        makeRenderSegment("s2", 1, 2, 4, { lifecycleState: "waiting" }),
      ],
      selectedTaskId,
      cursorTimeSeconds: null,
    },
    frameStartMs: 0,
  };
  return { renderContext, ctx };
}

describe("TimelineSegmentRenderer", () => {
  it("draws each scene segment + records metrics", () => {
    const metrics = new TimelineSegmentMetrics();
    const renderer = new TimelineSegmentRenderer({ metrics });
    const { renderContext } = buildContext({});
    renderer.render(renderContext);
    const snap = metrics.snapshot();
    expect(snap.segmentsRendered).toBe(2);
    expect(snap.visibleSegmentsTotal).toBe(2);
  });

  it("counts overlapping segments on the same row", () => {
    const metrics = new TimelineSegmentMetrics();
    const renderer = new TimelineSegmentRenderer({ metrics });
    const { renderContext } = buildContext({
      segments: [makeRenderSegment("a", 0, 1, 5), makeRenderSegment("b", 0, 3, 6)],
    });
    renderer.render(renderContext);
    expect(metrics.snapshot().overlapsObserved).toBe(1);
  });

  it("counts culled segments outside the visible window", () => {
    const metrics = new TimelineSegmentMetrics();
    const renderer = new TimelineSegmentRenderer({ metrics });
    const { renderContext } = buildContext({
      segments: [
        makeRenderSegment("visible", 0, 1, 2),
        makeRenderSegment("offscreen", 0, 100, 110),
      ],
    });
    renderer.render(renderContext);
    expect(metrics.snapshot().segmentsCulled).toBe(1);
    expect(metrics.snapshot().visibleSegmentsTotal).toBe(1);
  });

  it("records warning + selection paints", () => {
    const metrics = new TimelineSegmentMetrics();
    const renderer = new TimelineSegmentRenderer({ metrics });
    const { renderContext } = buildContext({
      selectedTaskId: "task_0",
      segments: [
        makeRenderSegment("s", 0, 1, 3, {
          warningSeverity: "critical",
          taskId: "task_0",
        }),
      ],
    });
    renderer.render(renderContext);
    const snap = metrics.snapshot();
    expect(snap.warningsRendered).toBe(1);
    expect(snap.selectionsRendered).toBe(1);
  });

  it("syncs the column from a bound row layout", () => {
    const rowLayout = makeRowLayout({ labelColumnWidthPx: 150, columnGutterPx: 6 });
    const renderer = new TimelineSegmentRenderer({ rowLayout });
    const { renderContext } = buildContext({});
    renderer.render(renderContext);
    const layoutSnapshot = renderer.getLayout().resolve(renderContext.coords);
    expect(layoutSnapshot.timelineColumnX).toBeGreaterThan(0);
  });

  it("respects setEnabled", () => {
    const metrics = new TimelineSegmentMetrics();
    const renderer = new TimelineSegmentRenderer({ metrics });
    renderer.enabled = false;
    const { renderContext } = buildContext({});
    renderer.render(renderContext);
    expect(metrics.snapshot().segmentsRendered).toBe(0);
  });

  it("registers as a TimelineLayer at order 10 by default", () => {
    const renderer = new TimelineSegmentRenderer();
    expect(renderer.id).toBe("segments");
    expect(renderer.order).toBe(10);
    expect(renderer.enabled).toBe(true);
  });
});
