import { describe, expect, it } from "vitest";
import {
  edgeIntersectsViewport,
  intersectsViewport,
  type Viewport,
} from "@/dashboard/dependencies/AwaitDependencyGeometry";
import { virtualize } from "@/dashboard/dependencies/AwaitDependencyVirtualization";
import { nodeAt, neighborNodeId } from "@/dashboard/dependencies/AwaitDependencyHitTesting";
import type { LaidEdge, LaidNode } from "@/dashboard/dependencies/layout/AwaitDependencyLayout";

const viewport: Viewport = { x: 0, y: 0, width: 200, height: 200 };

function makeLaidNode(id: string, x: number, y: number): LaidNode {
  return {
    node: {
      id,
      kind: "task",
      label: id,
      state: "running",
      parentTaskId: null,
      childCount: 0,
      completedCount: 0,
      cancelledCount: 0,
      failedCount: 0,
      progressRatio: 0,
      exceptionType: null,
      durationSeconds: null,
    },
    layer: 0,
    rank: 0,
    x,
    y,
    width: 50,
    height: 30,
  };
}

function makeLaidEdge(fromX: number, fromY: number, toX: number, toY: number): LaidEdge {
  return {
    edge: {
      id: "e",
      kind: "fanout",
      fromId: "a",
      toId: "b",
      completed: false,
      cancelled: false,
      failed: false,
      childIndex: null,
    },
    fromX,
    fromY,
    toX,
    toY,
    dangling: false,
  };
}

describe("intersectsViewport", () => {
  it("returns true for nodes inside the viewport", () => {
    expect(intersectsViewport(makeLaidNode("n", 50, 50), viewport)).toBe(true);
  });

  it("returns false for nodes fully outside the viewport", () => {
    expect(intersectsViewport(makeLaidNode("n", 500, 500), viewport)).toBe(false);
  });
});

describe("edgeIntersectsViewport", () => {
  it("includes edges that touch the viewport", () => {
    expect(edgeIntersectsViewport(makeLaidEdge(10, 10, 100, 100), viewport)).toBe(true);
  });

  it("excludes edges fully outside", () => {
    expect(edgeIntersectsViewport(makeLaidEdge(300, 300, 400, 400), viewport)).toBe(false);
  });
});

describe("virtualize", () => {
  it("clips off-viewport content + reports overflow", () => {
    const laidNodes = Array.from({ length: 5 }, (_, i) => makeLaidNode(`n-${i}`, i * 50, 0));
    const frame = {
      laidNodes,
      laidEdges: [],
      width: 250,
      height: 50,
      layerCount: 1,
      cycleDetected: false,
    };
    const out = virtualize({ frame, viewport, maxNodes: 2, maxEdges: 100 });
    expect(out.visibleNodes.length).toBeLessThanOrEqual(2);
    expect(out.nodeOverflow).toBeGreaterThanOrEqual(1);
  });
});

describe("nodeAt", () => {
  it("returns the laid node whose AABB contains the pointer", () => {
    const laidNodes = [makeLaidNode("a", 10, 10), makeLaidNode("b", 100, 10)];
    expect(nodeAt(laidNodes, 30, 20)?.node.id).toBe("a");
    expect(nodeAt(laidNodes, 200, 200)).toBeNull();
  });
});

describe("neighborNodeId", () => {
  it("steps forward / backward through views", () => {
    const views = [{ id: "a" }, { id: "b" }, { id: "c" }] as unknown as Parameters<
      typeof neighborNodeId
    >[0];
    expect(neighborNodeId(views, null, 1)).toBe("a");
    expect(neighborNodeId(views, "a", 1)).toBe("b");
    expect(neighborNodeId(views, "c", 1)).toBe("c");
    expect(neighborNodeId(views, "a", -1)).toBe("a");
  });
});
