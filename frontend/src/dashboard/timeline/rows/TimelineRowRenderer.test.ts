import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { TimelineRowRenderer } from "@/dashboard/timeline/rows/TimelineRowRenderer";
import { TimelineRowMetrics } from "@/dashboard/timeline/rows/TimelineRowMetrics";
import { DEFAULT_TIMELINE_PALETTE } from "@/dashboard/timeline/rendering/TimelineColors";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { RenderContext } from "@/dashboard/timeline/rendering/TimelineLayer";
import {
  createRowFakeContext,
  installRowFakeCanvasContext,
} from "@/dashboard/timeline/rows/__fixtures__/mockCanvas";
import { normalizeRow } from "@/dashboard/timeline/rows/utils/normalizeRow";

let restoreCanvas: (() => void) | undefined;
beforeAll(() => {
  restoreCanvas = installRowFakeCanvasContext();
});
afterAll(() => {
  restoreCanvas?.();
});

function buildContext(rows: number, overrides: { selectedTaskId?: string | null } = {}) {
  const coords = new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 24 },
    { cssWidth: 600, cssHeight: 240, devicePixelRatio: 2 },
  );
  const ctx = createRowFakeContext() as unknown as CanvasRenderingContext2D;
  const sceneRows = Array.from({ length: rows }, (_, i) =>
    normalizeRow({
      rowIndex: i,
      taskId: `t${i}`,
      label: `Task ${i}`,
      state: i % 2 === 0 ? "running" : "waiting",
      depth: i % 3,
      coroutineName: `fn_${i}`,
    }),
  );
  const renderContext: RenderContext = {
    ctx,
    coords,
    palette: DEFAULT_TIMELINE_PALETTE,
    scene: {
      totalRows: rows,
      rows: sceneRows,
      segments: [],
      selectedTaskId: overrides.selectedTaskId ?? null,
      cursorTimeSeconds: null,
    },
    frameStartMs: 0,
  };
  return { renderContext, ctx };
}

describe("TimelineRowRenderer", () => {
  it("exposes background + foreground passes at deterministic orders", () => {
    const renderer = new TimelineRowRenderer();
    expect(renderer.background.order).toBe(5);
    expect(renderer.foreground.order).toBe(25);
    expect(renderer.layers).toHaveLength(2);
  });

  it("renders backgrounds + decorators for every visible row", () => {
    const metrics = new TimelineRowMetrics();
    const renderer = new TimelineRowRenderer({ metrics });
    const { renderContext } = buildContext(4);
    renderer.background.render(renderContext);
    const snap = metrics.snapshot();
    expect(snap.rowsRendered).toBe(4);
    expect(snap.visibleRowsTotal).toBe(4);
  });

  it("paints the opaque label column once per foreground pass", () => {
    const renderer = new TimelineRowRenderer();
    const { renderContext, ctx } = buildContext(3);
    renderer.foreground.render(renderContext);
    // The label column fill + divider both call fillRect / stroke.
    expect(
      (ctx.fillRect as unknown as { mock: { calls: unknown[] } }).mock.calls.length,
    ).toBeGreaterThan(0);
  });

  it("records selection metrics when the selected row is on screen", () => {
    const metrics = new TimelineRowMetrics();
    const renderer = new TimelineRowRenderer({ metrics });
    const { renderContext } = buildContext(3, { selectedTaskId: "t1" });
    renderer.foreground.render(renderContext);
    expect(metrics.snapshot().selectionsRendered).toBe(1);
  });

  it("does nothing when there are no rows", () => {
    const metrics = new TimelineRowMetrics();
    const renderer = new TimelineRowRenderer({ metrics });
    const { renderContext } = buildContext(0);
    renderer.background.render(renderContext);
    renderer.foreground.render(renderContext);
    expect(metrics.snapshot().rowsRendered).toBe(0);
  });

  it("toggles both passes together via setEnabled", () => {
    const renderer = new TimelineRowRenderer();
    renderer.setEnabled(false);
    expect(renderer.background.enabled).toBe(false);
    expect(renderer.foreground.enabled).toBe(false);
    renderer.setEnabled(true);
    expect(renderer.background.enabled).toBe(true);
    expect(renderer.foreground.enabled).toBe(true);
  });

  it("renders warning chips when a row carries an active warning", () => {
    const metrics = new TimelineRowMetrics();
    const renderer = new TimelineRowRenderer({ metrics });
    const { renderContext } = buildContext(2);
    renderContext.scene.rows = [
      normalizeRow({
        rowIndex: 0,
        taskId: "t0",
        label: "task 0",
        state: "running",
        warningSeverity: "critical",
        warningCount: 3,
      }),
      normalizeRow({
        rowIndex: 1,
        taskId: "t1",
        label: "task 1",
        state: "running",
      }),
    ];
    renderer.background.render(renderContext);
    expect(metrics.snapshot().warningsRendered).toBe(1);
  });

  it("flags replay-marked frames in the metrics", () => {
    const metrics = new TimelineRowMetrics();
    const renderer = new TimelineRowRenderer({ metrics });
    const { renderContext } = buildContext(1);
    renderContext.scene.rows = [
      normalizeRow({
        rowIndex: 0,
        taskId: "t0",
        label: "task 0",
        state: "running",
        replay: { sequence: 99, focused: true },
      }),
    ];
    renderer.background.render(renderContext);
    expect(metrics.snapshot().replayMarkedFrames).toBe(1);
  });
});
