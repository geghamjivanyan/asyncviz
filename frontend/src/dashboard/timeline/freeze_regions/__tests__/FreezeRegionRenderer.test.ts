/**
 * End-to-end render test for the canonical FreezeRegionRenderer.
 *
 * Drives the renderer against a stubbed CanvasRenderingContext2D that
 * records every API call. Assertions are on the recorded calls (no
 * jsdom canvas binding) — that keeps the test deterministic and
 * cheap.
 */

import { beforeEach, describe, expect, it } from "vitest";
import { FreezeRegionRenderer } from "@/dashboard/timeline/freeze_regions/FreezeRegionRenderer";
import type { FreezeRegionSource } from "@/dashboard/timeline/freeze_regions/FreezeRegionRenderer";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { DEFAULT_TIMELINE_PALETTE } from "@/dashboard/timeline/rendering/TimelineColors";
import {
  resetFreezeRegionMetrics,
  getFreezeRegionMetrics,
} from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionMetricsCollector";
import { makeFreezeRegionView } from "@/dashboard/timeline/freeze_regions/__fixtures__/makeFreezeRegionFixtures";
import type { FreezeHitTestEntry } from "@/dashboard/timeline/freeze_regions/FreezeRegionHitTesting";
import type { FreezeRegionView } from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

interface CallRecord {
  op: string;
  args: unknown[];
}

function stubContext(): {
  ctx: CanvasRenderingContext2D;
  calls: CallRecord[];
  state: Record<string, unknown>;
} {
  const calls: CallRecord[] = [];
  const state: Record<string, unknown> = {};
  const setter = (key: string) => (value: unknown) => {
    state[key] = value;
    calls.push({ op: `set:${key}`, args: [value] });
  };
  const op =
    (name: string) =>
    (...args: unknown[]) => {
      calls.push({ op: name, args });
    };
  const proxy: Record<string, unknown> = {};
  for (const op of [
    "fillRect",
    "strokeRect",
    "beginPath",
    "moveTo",
    "lineTo",
    "stroke",
    "save",
    "restore",
    "setLineDash",
  ]) {
    proxy[op] = (...args: unknown[]) => {
      calls.push({ op, args });
    };
  }
  Object.defineProperties(proxy, {
    fillStyle: { set: setter("fillStyle") },
    strokeStyle: { set: setter("strokeStyle") },
    lineWidth: { set: setter("lineWidth") },
    globalAlpha: { set: setter("globalAlpha") },
  });
  void op; // unused helper retained for symmetry
  return { ctx: proxy as unknown as CanvasRenderingContext2D, calls, state };
}

function coords(timeStart: number, timeEnd: number, cssWidth = 1000) {
  return new TimelineCoordinateSystem(
    { timeStart, timeEnd, rowStart: 0, rowHeight: 18 },
    { cssWidth, cssHeight: 400, devicePixelRatio: 1 },
  );
}

interface StaticSourceState {
  regions: readonly FreezeRegionView[];
  selectedGroupId: string | null;
  hoveredGroupId: string | null;
  revealedGroupId: string | null;
  reducedMotion: boolean;
  cap: number;
  visibleEntries: readonly FreezeHitTestEntry[];
  hiddenCount: number;
}

function makeSource(initial: Partial<StaticSourceState> = {}): {
  source: FreezeRegionSource;
  state: StaticSourceState;
} {
  const state: StaticSourceState = {
    regions: [],
    selectedGroupId: null,
    hoveredGroupId: null,
    revealedGroupId: null,
    reducedMotion: false,
    cap: 0,
    visibleEntries: [],
    hiddenCount: 0,
    ...initial,
  };
  const source: FreezeRegionSource = {
    getRegions: () => state.regions,
    getSelectedGroupId: () => state.selectedGroupId,
    getHoveredGroupId: () => state.hoveredGroupId,
    getRevealedGroupId: () => state.revealedGroupId,
    isReducedMotion: () => state.reducedMotion,
    getVisibleCap: () => state.cap,
  };
  return { source, state };
}

beforeEach(() => {
  resetFreezeRegionMetrics();
});

describe("FreezeRegionRenderer", () => {
  it("draws one fill + one stroke per visible region", () => {
    const region = makeFreezeRegionView({ startSeconds: 1, endSeconds: 3 });
    const { source } = makeSource({ regions: [region] });
    const renderer = new FreezeRegionRenderer({ clock: () => 0 });
    renderer.setSource(source);
    const { ctx, calls } = stubContext();
    renderer.render({
      ctx,
      coords: coords(0, 10),
      palette: DEFAULT_TIMELINE_PALETTE,
      scene: {
        totalRows: 0,
        rows: [],
        segments: [],
        selectedTaskId: null,
        cursorTimeSeconds: null,
      },
      frameStartMs: 0,
    });
    const fills = calls.filter((c) => c.op === "fillRect");
    const strokes = calls.filter((c) => c.op === "strokeRect");
    expect(fills.length).toBe(1);
    expect(strokes.length).toBe(1);
  });

  it("skips drawing when the layer is disabled", () => {
    const region = makeFreezeRegionView();
    const { source } = makeSource({ regions: [region] });
    const renderer = new FreezeRegionRenderer({ enabled: false, clock: () => 0 });
    renderer.setSource(source);
    const { ctx, calls } = stubContext();
    renderer.render({
      ctx,
      coords: coords(0, 10),
      palette: DEFAULT_TIMELINE_PALETTE,
      scene: {
        totalRows: 0,
        rows: [],
        segments: [],
        selectedTaskId: null,
        cursorTimeSeconds: null,
      },
      frameStartMs: 0,
    });
    expect(calls.length).toBe(0);
  });

  it("publishes visible entries via onVisibleEntries", () => {
    const region = makeFreezeRegionView({ startSeconds: 1, endSeconds: 2 });
    const { source } = makeSource({ regions: [region] });
    let published: { count: number; hidden: number } = { count: -1, hidden: -1 };
    const renderer = new FreezeRegionRenderer({
      onVisibleEntries: (entries, hidden) => {
        published = { count: entries.length, hidden };
      },
      clock: () => 0,
    });
    renderer.setSource(source);
    const { ctx } = stubContext();
    renderer.render({
      ctx,
      coords: coords(0, 10),
      palette: DEFAULT_TIMELINE_PALETTE,
      scene: {
        totalRows: 0,
        rows: [],
        segments: [],
        selectedTaskId: null,
        cursorTimeSeconds: null,
      },
      frameStartMs: 0,
    });
    expect(published).toEqual({ count: 1, hidden: 0 });
  });

  it("emits a 'visible cap exceeded' signal when truncating", () => {
    const regions = Array.from({ length: 5 }, (_, i) =>
      makeFreezeRegionView({ groupId: `g-${i}`, startSeconds: i, endSeconds: i + 0.5 }),
    );
    const { source } = makeSource({ regions, cap: 2 });
    let hidden = 0;
    const renderer = new FreezeRegionRenderer({
      onVisibleEntries: (_, h) => {
        hidden = h;
      },
      clock: () => 0,
    });
    renderer.setSource(source);
    const { ctx } = stubContext();
    renderer.render({
      ctx,
      coords: coords(0, 10),
      palette: DEFAULT_TIMELINE_PALETTE,
      scene: {
        totalRows: 0,
        rows: [],
        segments: [],
        selectedTaskId: null,
        cursorTimeSeconds: null,
      },
      frameStartMs: 0,
    });
    expect(hidden).toBe(3);
  });

  it("is deterministic — two identical frames produce identical call sequences", () => {
    const region = makeFreezeRegionView({ startSeconds: 1, endSeconds: 3 });
    const { source } = makeSource({ regions: [region], reducedMotion: true });
    const renderer = new FreezeRegionRenderer({ clock: () => 1000 });
    renderer.setSource(source);
    const a = stubContext();
    const b = stubContext();
    const ctx = coords(0, 10);
    const sceneArg = {
      totalRows: 0,
      rows: [],
      segments: [],
      selectedTaskId: null,
      cursorTimeSeconds: null,
    };
    renderer.render({
      ctx: a.ctx,
      coords: ctx,
      palette: DEFAULT_TIMELINE_PALETTE,
      scene: sceneArg,
      frameStartMs: 0,
    });
    renderer.render({
      ctx: b.ctx,
      coords: ctx,
      palette: DEFAULT_TIMELINE_PALETTE,
      scene: sceneArg,
      frameStartMs: 0,
    });
    expect(a.calls).toEqual(b.calls);
  });

  it("updates the metrics collector once per frame", () => {
    const region = makeFreezeRegionView();
    const { source } = makeSource({ regions: [region] });
    const renderer = new FreezeRegionRenderer({ clock: () => 0 });
    renderer.setSource(source);
    const { ctx } = stubContext();
    renderer.render({
      ctx,
      coords: coords(0, 10),
      palette: DEFAULT_TIMELINE_PALETTE,
      scene: {
        totalRows: 0,
        rows: [],
        segments: [],
        selectedTaskId: null,
        cursorTimeSeconds: null,
      },
      frameStartMs: 0,
    });
    expect(getFreezeRegionMetrics().snapshot().framesRendered).toBe(1);
    expect(getFreezeRegionMetrics().snapshot().lastVisibleCount).toBe(1);
  });
});
