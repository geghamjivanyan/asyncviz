import { describe, expect, it, vi } from "vitest";
import { TimelineSelectionController } from "@/dashboard/timeline/selection/TimelineSelectionController";
import { TimelineSelectionMetrics } from "@/dashboard/timeline/selection/TimelineSelectionMetrics";
import {
  makeInMemoryStore,
  makeRows,
  makeTask,
} from "@/dashboard/timeline/selection/__fixtures__/makeSelectionFixtures";

function setup(options: { initial?: string | null; rowCount?: number } = {}) {
  const store = makeInMemoryStore(options.initial ?? null);
  const rows = makeRows(options.rowCount ?? 3);
  const taskMap = new Map(rows.map((r) => [r.taskId, makeTask(r.taskId)]));
  const metrics = new TimelineSelectionMetrics();
  const controller = new TimelineSelectionController({
    store,
    metrics,
    rows: {
      getRows: () => rows,
      getTask: (id) => (id === null ? null : (taskMap.get(id) ?? null)),
      getTaskRange: () => ({ startSeconds: 0, endSeconds: 1 }),
    },
  });
  return { controller, store, rows, metrics };
}

describe("TimelineSelectionController", () => {
  it("starts with the store's initial selection", () => {
    const { controller } = setup({ initial: "t1" });
    expect(controller.currentState().selectedTaskId).toBe("t1");
    expect(controller.currentState().selectedRowIndex).toBe(1);
  });

  it("selectRow writes to the store + emits state", () => {
    const { controller, store, metrics } = setup();
    const listener = vi.fn();
    controller.subscribe(listener);
    controller.selectRow("t1");
    expect(store.getSelectedTaskId()).toBe("t1");
    expect(controller.currentState().selectedTaskId).toBe("t1");
    expect(listener).toHaveBeenCalled();
    expect(metrics.snapshot().programmaticSelects).toBe(1);
  });

  it("selectRow with the same id is a noop", () => {
    const { controller, metrics } = setup({ initial: "t0" });
    controller.selectRow("t0");
    expect(metrics.snapshot().noopsSuppressed).toBe(1);
  });

  it("clearSelection nulls the store + records the metric", () => {
    const { controller, store, metrics } = setup({ initial: "t1" });
    controller.clearSelection();
    expect(store.getSelectedTaskId()).toBeNull();
    expect(metrics.snapshot().clears).toBe(1);
  });

  it("selectNext / selectPrevious navigate within the row list", () => {
    const { controller } = setup({ initial: "t1" });
    controller.selectNext();
    expect(controller.currentState().selectedTaskId).toBe("t2");
    controller.selectPrevious();
    expect(controller.currentState().selectedTaskId).toBe("t1");
  });

  it("selectFirst / selectLast jump to the row boundaries", () => {
    const { controller } = setup({ initial: "t1" });
    controller.selectFirst();
    expect(controller.currentState().selectedTaskId).toBe("t0");
    controller.selectLast();
    expect(controller.currentState().selectedTaskId).toBe("t2");
  });

  it("restoreSelection sets a hit + clears a miss", () => {
    const { controller, metrics } = setup({ initial: "t0" });
    controller.restoreSelection("t2");
    expect(controller.currentState().selectedTaskId).toBe("t2");
    expect(metrics.snapshot().restoreCalls).toBe(1);
    controller.restoreSelection("missing");
    expect(controller.currentState().selectedTaskId).toBeNull();
    expect(metrics.snapshot().restoreMisses).toBe(1);
  });

  it("emits a state when the store changes externally", () => {
    const { controller, store } = setup();
    const listener = vi.fn();
    controller.subscribe(listener);
    store.setSelectedTaskId("t1");
    expect(controller.currentState().selectedTaskId).toBe("t1");
    expect(listener).toHaveBeenCalled();
  });

  it("centerOnSelection calls the focus adapter when configured", () => {
    const store = makeInMemoryStore("t1");
    const focus = { panToTimeStart: vi.fn(), fitToRange: vi.fn() };
    const rows = makeRows(3);
    const controller = new TimelineSelectionController({
      store,
      rows: {
        getRows: () => rows,
        getTask: () => null,
        getTaskRange: () => ({ startSeconds: 4, endSeconds: 8 }),
      },
      viewport: {
        getViewport: () => ({
          visibleStartSeconds: 0,
          visibleEndSeconds: 10,
          durationSeconds: 10,
        }),
      },
      focus,
    });
    controller.centerOnSelection();
    expect(focus.panToTimeStart).toHaveBeenCalledWith(1);
  });

  it("revealSelection no-ops when the selection is already visible", () => {
    const store = makeInMemoryStore("t1");
    const focus = { panToTimeStart: vi.fn(), fitToRange: vi.fn() };
    const rows = makeRows(3);
    const controller = new TimelineSelectionController({
      store,
      rows: {
        getRows: () => rows,
        getTask: () => null,
        getTaskRange: () => ({ startSeconds: 4, endSeconds: 6 }),
      },
      viewport: {
        getViewport: () => ({
          visibleStartSeconds: 0,
          visibleEndSeconds: 10,
          durationSeconds: 10,
        }),
      },
      focus,
    });
    controller.revealSelection();
    expect(focus.panToTimeStart).not.toHaveBeenCalled();
  });

  it("fitToSelection delegates to the focus adapter", () => {
    const store = makeInMemoryStore("t1");
    const focus = { panToTimeStart: vi.fn(), fitToRange: vi.fn() };
    const rows = makeRows(3);
    const controller = new TimelineSelectionController({
      store,
      rows: {
        getRows: () => rows,
        getTask: () => null,
        getTaskRange: () => ({ startSeconds: 4, endSeconds: 8 }),
      },
      focus,
    });
    controller.fitToSelection();
    expect(focus.fitToRange).toHaveBeenCalledWith(4, 8);
  });

  it("dispose detaches from the store", () => {
    const { controller, store } = setup({ initial: "t0" });
    controller.dispose();
    store.setSelectedTaskId("t2");
    expect(controller.currentState().selectedTaskId).toBe("t0");
  });
});
