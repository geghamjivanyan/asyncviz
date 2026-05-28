import { describe, expect, it } from "vitest";
import { layoutDependencies } from "@/dashboard/dependencies/layout/AwaitDependencyLayout";
import { projectDependencies } from "@/dashboard/dependencies/AwaitDependencyProjection";
import {
  makeEdge,
  makeNode,
} from "@/dashboard/dependencies/__fixtures__/awaitDependencyFixtures";

function viewsOf(nodes: ReturnType<typeof makeNode>[], edges: ReturnType<typeof makeEdge>[]) {
  return projectDependencies({ nodes, edges });
}

describe("layoutDependencies", () => {
  it("returns an empty frame for empty input", () => {
    const frame = layoutDependencies({ nodes: [], edges: [] });
    expect(frame.laidNodes).toEqual([]);
    expect(frame.laidEdges).toEqual([]);
    expect(frame.layerCount).toBe(0);
  });

  it("assigns roots to layer 0 + children to layer 1", () => {
    const records = [
      makeNode({ id: "root", kind: "task" }),
      makeNode({ id: "g-1", kind: "gather", parentTaskId: "root" }),
      makeNode({ id: "leaf", kind: "task" }),
    ];
    const edges = [
      makeEdge({ id: "awaits:root->g-1", kind: "awaits", fromId: "root", toId: "g-1" }),
      makeEdge({ id: "fanout:g-1->leaf", fromId: "g-1", toId: "leaf" }),
    ];
    const { nodes: views, edges: edgeViews } = viewsOf(records, edges);
    const frame = layoutDependencies({ nodes: views, edges: edgeViews });
    const layerByNode = Object.fromEntries(
      frame.laidNodes.map((n) => [n.node.id, n.layer]),
    );
    expect(layerByNode["root"]).toBe(0);
    expect(layerByNode["g-1"]).toBe(1);
    expect(layerByNode["leaf"]).toBe(2);
    expect(frame.layerCount).toBe(3);
  });

  it("orders layer members by ordering hint when provided", () => {
    const records = [
      makeNode({ id: "a", kind: "task" }),
      makeNode({ id: "b", kind: "task" }),
      makeNode({ id: "c", kind: "task" }),
    ];
    const { nodes: views } = viewsOf(records, []);
    const frame = layoutDependencies({
      nodes: views,
      edges: [],
      ordering: ["c", "a", "b"],
    });
    const order = frame.laidNodes.map((n) => n.node.id);
    expect(order).toEqual(["c", "a", "b"]);
  });

  it("falls back to alphabetic ordering when no hint is supplied", () => {
    const records = [
      makeNode({ id: "delta", kind: "task" }),
      makeNode({ id: "alpha", kind: "task" }),
      makeNode({ id: "charlie", kind: "task" }),
    ];
    const { nodes: views } = viewsOf(records, []);
    const frame = layoutDependencies({ nodes: views, edges: [] });
    const order = frame.laidNodes.map((n) => n.node.id);
    expect(order).toEqual(["alpha", "charlie", "delta"]);
  });

  it("detects cycles + still produces a layout", () => {
    const records = [
      makeNode({ id: "a", kind: "task" }),
      makeNode({ id: "b", kind: "task" }),
    ];
    const edges = [
      makeEdge({ id: "fanout:a->b", fromId: "a", toId: "b" }),
      makeEdge({ id: "fanout:b->a", fromId: "b", toId: "a" }),
    ];
    const { nodes: views, edges: edgeViews } = viewsOf(records, edges);
    const frame = layoutDependencies({ nodes: views, edges: edgeViews });
    expect(frame.cycleDetected).toBe(true);
    expect(frame.laidNodes.length).toBe(2);
  });

  it("flags dangling edges (missing endpoint nodes)", () => {
    const records = [makeNode({ id: "a", kind: "task" })];
    const edges = [
      makeEdge({ id: "fanout:a->missing", fromId: "a", toId: "missing" }),
    ];
    const { nodes: views, edges: edgeViews } = viewsOf(records, edges);
    const frame = layoutDependencies({ nodes: views, edges: edgeViews });
    // Adjacency builder skips the edge for layering, but layout still
    // emits one entry flagged ``dangling`` so the renderer can decide
    // whether to draw it.
    expect(frame.laidEdges).toHaveLength(1);
    expect(frame.laidEdges[0].dangling).toBe(true);
  });

  it("is deterministic across repeated calls with the same inputs", () => {
    const records = [
      makeNode({ id: "root", kind: "task" }),
      makeNode({ id: "g-1", kind: "gather", parentTaskId: "root" }),
      makeNode({ id: "leaf", kind: "task" }),
    ];
    const edges = [
      makeEdge({ id: "awaits:root->g-1", kind: "awaits", fromId: "root", toId: "g-1" }),
      makeEdge({ id: "fanout:g-1->leaf", fromId: "g-1", toId: "leaf" }),
    ];
    const { nodes: views, edges: edgeViews } = viewsOf(records, edges);
    const first = layoutDependencies({ nodes: views, edges: edgeViews });
    const second = layoutDependencies({ nodes: views, edges: edgeViews });
    expect(first.laidNodes.map((n) => [n.node.id, n.x, n.y])).toEqual(
      second.laidNodes.map((n) => [n.node.id, n.x, n.y]),
    );
  });
});
