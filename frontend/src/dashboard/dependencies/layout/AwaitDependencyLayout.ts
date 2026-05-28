/**
 * Layered DAG layout for the await dependency graph.
 *
 * Algorithm (BFS-style longest-path layering):
 *
 *   1. Build an adjacency map (``from -> [to, ...]``) + an in-degree
 *      map from the projection's edges.
 *   2. Seed a frontier with every zero-in-degree node (roots). Assign
 *      them layer 0.
 *   3. Pop nodes from the frontier; for each outgoing edge, decrement
 *      the child's pending in-degree counter. When it reaches zero,
 *      the child's layer = max(parent layers) + 1 and we push it.
 *   4. Cycle-safe: any node still un-layered after the BFS (because of
 *      a cycle introduced by stale state) lands at layer 0 with a flag
 *      so the renderer can show it without infinite loops.
 *
 * Within a layer, nodes are sorted by ``firstSeenNs`` then by ``id`` so
 * the layout is stable across renders — adding a new sibling doesn't
 * jiggle the existing layout.
 *
 * The output is a flat array of :type:`LaidNode` + :type:`LaidEdge`
 * (with screen-space coordinates). The renderer wraps each in a focusable
 * DOM/SVG element.
 */

import type {
  AwaitEdgeView,
  AwaitNodeView,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";

export interface LayoutInputs {
  nodes: ReadonlyArray<AwaitNodeView>;
  edges: ReadonlyArray<AwaitEdgeView>;
  /** Optional ordering hint — when supplied, defines stable in-layer
   *  ordering. Defaults to the input node array order, which the store
   *  keeps in insertion order (first-seen). */
  ordering?: ReadonlyArray<string>;
  layerSpacing?: number;
  nodeSpacing?: number;
  nodeWidth?: number;
  nodeHeight?: number;
  /** Padding around the bounding box, in CSS pixels. */
  padding?: number;
}

export interface LaidNode {
  node: AwaitNodeView;
  layer: number;
  /** Position within the layer, from top. */
  rank: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LaidEdge {
  edge: AwaitEdgeView;
  /** Screen-space coords for the source + sink anchor points. */
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  /** ``true`` when either endpoint is missing from the layout (e.g. an
   *  edge to a node we evicted). Renderers skip drawing these. */
  dangling: boolean;
}

export interface LayoutFrame {
  laidNodes: LaidNode[];
  laidEdges: LaidEdge[];
  width: number;
  height: number;
  layerCount: number;
  /** ``true`` when at least one node fell into the cycle-safe layer 0
   *  bucket because of a topology cycle. The renderer can surface a
   *  diagnostic in that case. */
  cycleDetected: boolean;
}

const DEFAULTS = {
  layerSpacing: 220,
  nodeSpacing: 72,
  nodeWidth: 180,
  nodeHeight: 56,
  padding: 24,
} as const;

function buildAdjacency(
  nodes: ReadonlyArray<AwaitNodeView>,
  edges: ReadonlyArray<AwaitEdgeView>,
): {
  outgoing: Map<string, string[]>;
  inDegree: Map<string, number>;
} {
  const outgoing = new Map<string, string[]>();
  const inDegree = new Map<string, number>();
  for (const node of nodes) {
    outgoing.set(node.id, []);
    inDegree.set(node.id, 0);
  }
  for (const edge of edges) {
    if (!outgoing.has(edge.fromId) || !inDegree.has(edge.toId)) continue;
    outgoing.get(edge.fromId)!.push(edge.toId);
    inDegree.set(edge.toId, (inDegree.get(edge.toId) ?? 0) + 1);
  }
  return { outgoing, inDegree };
}

function assignLayers(
  nodes: ReadonlyArray<AwaitNodeView>,
  outgoing: Map<string, string[]>,
  inDegree: Map<string, number>,
): { layers: Map<string, number>; cycleDetected: boolean } {
  const layers = new Map<string, number>();
  const remainingInDegree = new Map(inDegree);
  // Stable frontier — keeps seed order deterministic.
  const frontier: string[] = [];
  for (const node of nodes) {
    if ((remainingInDegree.get(node.id) ?? 0) === 0) {
      layers.set(node.id, 0);
      frontier.push(node.id);
    }
  }
  while (frontier.length > 0) {
    const next = frontier.shift()!;
    const fromLayer = layers.get(next) ?? 0;
    for (const childId of outgoing.get(next) ?? []) {
      const previousLayer = layers.get(childId);
      const newLayer = Math.max(fromLayer + 1, previousLayer ?? 0);
      layers.set(childId, newLayer);
      const pending = (remainingInDegree.get(childId) ?? 1) - 1;
      remainingInDegree.set(childId, pending);
      if (pending === 0) {
        frontier.push(childId);
      }
    }
  }
  // Anything not laid out implies a cycle — pin to layer 0 as a defensive
  // fallback so the render still draws them.
  let cycleDetected = false;
  for (const node of nodes) {
    if (!layers.has(node.id)) {
      cycleDetected = true;
      layers.set(node.id, 0);
    }
  }
  return { layers, cycleDetected };
}

/** Stable in-layer ordering: ordering hint first, then alphabetic. */
function sortLayer(
  ids: string[], ordering?: ReadonlyArray<string>,
): string[] {
  if (ordering === undefined) {
    return [...ids].sort();
  }
  const rank = new Map<string, number>();
  ordering.forEach((id, i) => rank.set(id, i));
  return [...ids].sort((a, b) => {
    const ra = rank.get(a);
    const rb = rank.get(b);
    if (ra !== undefined && rb !== undefined) return ra - rb;
    if (ra !== undefined) return -1;
    if (rb !== undefined) return 1;
    return a < b ? -1 : a > b ? 1 : 0;
  });
}

export function layoutDependencies(inputs: LayoutInputs): LayoutFrame {
  const {
    nodes,
    edges,
    ordering,
    layerSpacing = DEFAULTS.layerSpacing,
    nodeSpacing = DEFAULTS.nodeSpacing,
    nodeWidth = DEFAULTS.nodeWidth,
    nodeHeight = DEFAULTS.nodeHeight,
    padding = DEFAULTS.padding,
  } = inputs;
  if (nodes.length === 0) {
    return {
      laidNodes: [],
      laidEdges: [],
      width: padding * 2,
      height: padding * 2,
      layerCount: 0,
      cycleDetected: false,
    };
  }
  const { outgoing, inDegree } = buildAdjacency(nodes, edges);
  const { layers, cycleDetected } = assignLayers(nodes, outgoing, inDegree);

  // Bucket nodes per layer.
  const buckets = new Map<number, string[]>();
  for (const node of nodes) {
    const layer = layers.get(node.id) ?? 0;
    if (!buckets.has(layer)) buckets.set(layer, []);
    buckets.get(layer)!.push(node.id);
  }
  const layerCount = Math.max(...buckets.keys()) + 1;

  // Position each node.
  const laidNodes: LaidNode[] = [];
  const positionsById = new Map<string, LaidNode>();
  for (let layer = 0; layer < layerCount; layer += 1) {
    const ids = sortLayer(buckets.get(layer) ?? [], ordering);
    ids.forEach((id, rank) => {
      const node = nodes.find((n) => n.id === id)!;
      const x = padding + layer * layerSpacing;
      const y = padding + rank * (nodeHeight + nodeSpacing);
      const laid: LaidNode = {
        node,
        layer,
        rank,
        x,
        y,
        width: nodeWidth,
        height: nodeHeight,
      };
      laidNodes.push(laid);
      positionsById.set(id, laid);
    });
  }

  // Edge geometry — right edge of source to left edge of sink.
  const laidEdges: LaidEdge[] = edges.map((edge) => {
    const from = positionsById.get(edge.fromId);
    const to = positionsById.get(edge.toId);
    if (from === undefined || to === undefined) {
      return {
        edge,
        fromX: 0,
        fromY: 0,
        toX: 0,
        toY: 0,
        dangling: true,
      };
    }
    return {
      edge,
      fromX: from.x + from.width,
      fromY: from.y + from.height / 2,
      toX: to.x,
      toY: to.y + to.height / 2,
      dangling: false,
    };
  });

  const width =
    padding * 2 + (layerCount - 1) * layerSpacing + nodeWidth;
  const maxBucketSize = Math.max(
    1,
    ...Array.from(buckets.values()).map((b) => b.length),
  );
  const height =
    padding * 2 + maxBucketSize * nodeHeight
    + (maxBucketSize - 1) * nodeSpacing;

  return { laidNodes, laidEdges, width, height, layerCount, cycleDetected };
}
