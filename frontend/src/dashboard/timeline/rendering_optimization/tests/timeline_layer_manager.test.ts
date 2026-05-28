import { describe, expect, it } from "vitest";
import { TimelineLayerManager } from "../timeline_layer_manager";
import { RenderPriority } from "../models";

const dataLayer = {
  id: "data",
  priority: RenderPriority.NORMAL,
  invalidatedBy: new Set(["data" as const, "camera" as const]),
  label: "data layer",
};
const overlayLayer = {
  id: "overlay:cursor",
  priority: RenderPriority.HIGH,
  invalidatedBy: new Set(["cursor" as const, "overlay" as const]),
  label: "cursor overlay",
};

const region = {
  x: 0,
  y: 0,
  width: 100,
  height: 100,
  reason: "data" as const,
};

describe("TimelineLayerManager", () => {
  it("starts with no layers", () => {
    const m = new TimelineLayerManager();
    expect(m.collectPasses()).toHaveLength(0);
  });

  it("registers layers + reports them dirty by default", () => {
    const m = new TimelineLayerManager();
    m.register(dataLayer);
    expect(m.has("data")).toBe(true);
    const passes = m.collectPasses();
    expect(passes).toHaveLength(1);
  });

  it("invalidates only layers subscribed to the reason", () => {
    const m = new TimelineLayerManager();
    m.register(dataLayer);
    m.register(overlayLayer);
    m.acknowledgeAll();
    m.invalidate({ ...region, reason: "data" });
    const passes = m.collectPasses();
    expect(passes.map((p) => p.id)).toEqual(["data"]);
  });

  it("orders passes by priority descending", () => {
    const m = new TimelineLayerManager();
    m.register(dataLayer);
    m.register(overlayLayer);
    const passes = m.collectPasses();
    expect(passes[0]!.id).toBe("overlay:cursor");
    expect(passes[1]!.id).toBe("data");
  });

  it("invalidateAll marks every layer dirty", () => {
    const m = new TimelineLayerManager();
    m.register(dataLayer);
    m.register(overlayLayer);
    m.acknowledgeAll();
    m.invalidateAll({ ...region, reason: "viewport" });
    expect(m.collectPasses()).toHaveLength(2);
  });

  it("acknowledge clears the dirty bit on one layer", () => {
    const m = new TimelineLayerManager();
    m.register(dataLayer);
    m.acknowledge("data");
    expect(m.collectPasses()).toHaveLength(0);
  });

  it("rejects duplicate registration", () => {
    const m = new TimelineLayerManager();
    m.register(dataLayer);
    expect(() => m.register(dataLayer)).toThrow();
  });

  it("describe lists every registered layer with its dirty state", () => {
    const m = new TimelineLayerManager();
    m.register(dataLayer);
    m.acknowledgeAll();
    m.invalidate({ ...region, reason: "data" });
    const desc = m.describe();
    expect(desc).toHaveLength(1);
    expect(desc[0]!.dirty).toBe(true);
  });
});
