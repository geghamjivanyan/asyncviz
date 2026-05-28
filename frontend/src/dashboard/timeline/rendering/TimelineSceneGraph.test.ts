import { describe, expect, it, vi } from "vitest";
import { TimelineSceneGraph } from "@/dashboard/timeline/rendering/TimelineSceneGraph";
import type { RenderContext, TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";

function makeLayer(
  id: string,
  order: number,
): { layer: TimelineLayer; spy: ReturnType<typeof vi.fn> } {
  const spy = vi.fn();
  return {
    layer: { id, order, enabled: true, render: spy },
    spy,
  };
}

describe("TimelineSceneGraph", () => {
  it("renders layers in ascending order", () => {
    const graph = new TimelineSceneGraph();
    const order: string[] = [];
    const ctx = {} as unknown as RenderContext;
    const a = { id: "a", order: 10, enabled: true, render: () => order.push("a") };
    const b = { id: "b", order: 0, enabled: true, render: () => order.push("b") };
    const c = { id: "c", order: 5, enabled: true, render: () => order.push("c") };
    graph.addLayer(a);
    graph.addLayer(b);
    graph.addLayer(c);
    graph.renderAll(ctx);
    expect(order).toEqual(["b", "c", "a"]);
  });

  it("skips disabled layers", () => {
    const graph = new TimelineSceneGraph();
    const { layer, spy } = makeLayer("x", 0);
    layer.enabled = false;
    graph.addLayer(layer);
    graph.renderAll({} as unknown as RenderContext);
    expect(spy).not.toHaveBeenCalled();
  });

  it("toggles enabled by id", () => {
    const graph = new TimelineSceneGraph();
    const { layer, spy } = makeLayer("x", 0);
    graph.addLayer(layer);
    graph.setLayerEnabled("x", false);
    graph.renderAll({} as unknown as RenderContext);
    expect(spy).not.toHaveBeenCalled();
  });

  it("rejects duplicate ids", () => {
    const graph = new TimelineSceneGraph();
    graph.addLayer(makeLayer("x", 0).layer);
    expect(() => graph.addLayer(makeLayer("x", 1).layer)).toThrow();
  });

  it("removeLayer removes the layer", () => {
    const graph = new TimelineSceneGraph();
    graph.addLayer(makeLayer("x", 0).layer);
    graph.removeLayer("x");
    expect(graph.layerIds()).toEqual([]);
  });
});
